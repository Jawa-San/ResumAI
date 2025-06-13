from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
import os
import re
import json
import hashlib
import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import black, darkblue, gray
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Configure folders
UPLOAD_FOLDER = 'uploads'
CACHE_FOLDER = 'cache'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CACHE_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CACHE_FOLDER'] = CACHE_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Initialize OpenAI client with API key from environment variable
openai_api_key = os.getenv('OPENAI_API_KEY')
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")
openai_client = OpenAI(api_key=openai_api_key)

def create_safe_filename(name, fallback="Resume"):
    """Create a safe filename from a person's name"""
    if not name or not name.strip():
        return fallback
    
    # Clean the name - remove special characters and replace spaces with underscores
    safe_name = re.sub(r'[^\w\s-]', '', name.strip())
    safe_name = re.sub(r'[-\s]+', '_', safe_name)
    
    # Ensure it's not too long
    if len(safe_name) > 50:
        safe_name = safe_name[:50]
    
    # Remove trailing underscores
    safe_name = safe_name.strip('_')
    
    # If nothing left after cleaning, use fallback
    if not safe_name:
        return fallback
    
    return safe_name

class JobScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def scrape_job_description(self, url):
        """Scrape job description from various job sites"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Try different selectors based on common job sites
            job_content = self._extract_job_content(soup, url)
            
            if not job_content:
                # Fallback: get all text and let AI filter it
                job_content = soup.get_text()
            
            # Clean up the text
            lines = (line.strip() for line in job_content.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            job_content = ' '.join(chunk for chunk in chunks if chunk)
            
            return job_content[:8000]  # Limit to 8000 characters
            
        except Exception as e:
            print(f"Error scraping job: {e}")
            return None
    
    def _extract_job_content(self, soup, url):
        """Extract job content using site-specific selectors"""
        domain = urlparse(url).netloc.lower()
        
        # LinkedIn
        if 'linkedin.com' in domain:
            selectors = [
                '.jobs-description-content__text',
                '.jobs-box__html-content',
                '.description__text'
            ]
        # Indeed
        elif 'indeed.com' in domain:
            selectors = [
                '#jobDescriptionText',
                '.jobsearch-jobDescriptionText',
                '.jobsearch-JobComponent-description'
            ]
        # Glassdoor
        elif 'glassdoor.com' in domain:
            selectors = [
                '.jobDescriptionContent',
                '#JobDescriptionContainer',
                '.desc'
            ]
        # AngelList/Wellfound
        elif 'angel.co' in domain or 'wellfound.com' in domain:
            selectors = [
                '.job-description',
                '[data-test="JobDescription"]'
            ]
        # Monster
        elif 'monster.com' in domain:
            selectors = [
                '.job-description',
                '#JobDescription'
            ]
        # ZipRecruiter
        elif 'ziprecruiter.com' in domain:
            selectors = [
                '.jobDescriptionSection',
                '.job_description'
            ]
        else:
            # Generic selectors for other sites
            selectors = [
                '[class*="job-description"]',
                '[class*="description"]',
                '[id*="description"]',
                '[class*="content"]',
                'main',
                '.main-content'
            ]
        
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    return element.get_text()
            except:
                continue
        
        return None

class AIResumeParser:
    def __init__(self, openai_client):
        self.client = openai_client
    
    def parse_resume_with_ai(self, resume_text):
        """Use OpenAI to parse resume into structured JSON"""
        
        prompt = f"""
Parse the following resume text into a comprehensive JSON structure. Extract ALL information accurately and include everything present in the resume.

Resume text:
{resume_text}

Please return ONLY a valid JSON object with this structure (include ALL bullet points, projects, certifications, etc.):
{{
    "personal_info": {{
        "name": "Full name",
        "email": "email@example.com", 
        "phone": "phone number",
        "linkedin": "LinkedIn URL (clean format like https://linkedin.com/in/username)",
        "website": "personal website URL (clean format like https://example.com)",
        "github": "GitHub profile URL (clean format like https://github.com/username)",
        "location": "city, state if present"
    }},
    "summary": "Complete professional summary or objective (if present)",
    "skills": ["skill1", "skill2", "skill3", "etc - include ALL skills mentioned"],
    "experience": [
        {{
            "title": "Job title",
            "company": "Company name",
            "location": "Job location if mentioned",
            "dates": "Complete date range (e.g., Mar 2024 - Oct 2024)",
            "bullets": ["Include ALL bullet points and achievements", "Don't limit to just 2", "Include every responsibility and achievement listed"]
        }}
    ],
    "projects": [
        {{
            "name": "Project name",
            "description": "Project description - if there are bullet points, include them as separate items in the bullets array instead",
            "bullets": ["bullet point 1", "bullet point 2", "etc - ONLY if the project has bullet points"],
            "technologies": ["tech1", "tech2"],
            "url": "project URL in clean format (like https://github.com/user/project)",
            "dates": "project dates if present"
        }}
    ],
    "education": [
        {{
            "degree": "Complete degree name",
            "school": "Full institution name", 
            "location": "school location if present",
            "date": "graduation date",
            "gpa": "GPA if mentioned",
            "honors": "honors/distinctions if mentioned",
            "relevant_courses": ["course1", "course2"] 
        }}
    ],
    "certifications": ["cert1", "cert2", "etc"],
    "awards": ["award1", "award2", "etc"],
    "languages": ["language1", "language2", "etc"],
    "volunteer": [
        {{
            "role": "volunteer role",
            "organization": "organization name",
            "dates": "volunteer dates",
            "description": "what they did"
        }}
    ]
}}

CRITICAL INSTRUCTIONS FOR LINKS:
- Look for actual URLs or domain patterns in the resume text that reveal which username belongs to which platform
- If you see patterns like "username.github.io" or "github.com/username", that username belongs to GitHub
- If you see "linkedin.com/in/username", that username belongs to LinkedIn  
- Use these URL clues to correctly match usernames to platforms rather than guessing
- Cross-reference any standalone usernames with URL patterns found elsewhere in the resume
- If there are no URL clues, be conservative and don't assign platforms randomly

CRITICAL INSTRUCTIONS FOR PROJECTS:
- If a project has bullet points/achievements listed, put them in the "bullets" array
- If a project only has a description paragraph, put it in "description" 
- Don't duplicate content between description and bullets
- Look carefully at the formatting to determine if there are bullet points

CRITICAL INSTRUCTIONS FOR TEXT CLEANING:
- Replace any weird characters, black boxes, or special Unicode characters with appropriate standard characters
- Convert em-dashes, en-dashes, and other dash variants to regular hyphens (-)
- Replace any corrupted characters from PDF extraction with normal text
- Ensure all text uses standard ASCII characters where possible
- Fix any character encoding issues that create black boxes or strange symbols
- Clean up any formatting artifacts from PDF text extraction

OTHER CRITICAL INSTRUCTIONS:
- Include EVERY piece of information from the resume
- Don't summarize or shorten bullet points - include them completely
- If a section doesn't exist, use empty array [] or empty string ""
- Extract ALL skills, not just a few examples
- Include ALL work experience bullet points
- Include ALL projects if mentioned
- Include complete education details (GPA, honors, courses, etc.)
- Capture certifications, awards, languages if present
- Don't leave anything out
- Return only the JSON, no other text
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a comprehensive resume parsing expert. Extract ALL information from resumes into complete JSON format. Pay special attention to formatting URLs properly and detecting bullet points vs descriptions in projects. Never summarize or leave out details."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            
            # Extract the JSON from the response
            json_text = response.choices[0].message.content.strip()
            
            # Sometimes the API wraps JSON in markdown code blocks
            if json_text.startswith('```json'):
                json_text = json_text[7:-3]
            elif json_text.startswith('```'):
                json_text = json_text[3:-3]
            
            # Parse and return the JSON
            parsed_data = json.loads(json_text)
            return parsed_data
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Raw response: {json_text}")
            # Return a basic structure if JSON parsing fails
            return self._fallback_parse()
        except Exception as e:
            print(f"OpenAI API error: {e}")
            # Fallback to basic parsing
            return self._fallback_parse()
    
    def optimize_resume_for_job(self, resume_data, job_description, creativity_level=0.5):
        """Use AI to optimize resume based on job description"""
        
        # Convert creativity level (0-1) to temperature (0.1-1.2)
        temperature = 0.1 + (creativity_level * 1.1)
        
        prompt = f"""
You are an expert resume optimizer. Your job is to intelligently modify a resume to better match a specific job posting while maintaining accuracy and authenticity.

ORIGINAL RESUME DATA:
{json.dumps(resume_data, indent=2)}

JOB DESCRIPTION:
{job_description}

OPTIMIZATION INSTRUCTIONS:
1. Analyze the job description to identify key skills, technologies, requirements, and keywords
2. Modify the resume to better align with the job while keeping all information truthful
3. Add relevant keywords naturally into existing bullet points and descriptions
4. Reorder skills to prioritize those mentioned in the job description
5. Enhance bullet points to highlight relevant experience using job-specific language
6. Modify the professional summary to better target this role
7. Based on creativity level, add fake experience, skills, or qualifications
8. DO NOT change dates, company names, or core facts
9. {f"At maximum creativity (100%), you may modify job titles to better align with the target role while keeping the same company. For example, 'Software Developer' could become 'Full Stack Developer' or 'Frontend Engineer' if it better matches the job description." if creativity_level >= 1.0 else "Only enhance and reframe existing content without changing job titles"}

CREATIVITY LEVEL: {creativity_level} (0 = minimal changes, 1 = more creative optimization)

Return the optimized resume in the EXACT SAME JSON structure with the following changes:
- Enhanced professional summary targeting the role
- Reordered and enhanced skills list with job-relevant skills first
- Improved bullet points with job-relevant keywords and language
- Better alignment of existing experience with job requirements
{"- Modified job titles to better match target role (only at maximum creativity)" if creativity_level >= 1.0 else ""}
- Use only the best three bullet points for each experience and project

Return ONLY the JSON object, no other text.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert resume optimizer who enhances resumes to better match job descriptions while maintaining complete accuracy and truthfulness. You never add false information but intelligently reframe existing content."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=4000
            )
            
            # Extract the JSON from the response
            json_text = response.choices[0].message.content.strip()
            
            # Sometimes the API wraps JSON in markdown code blocks
            if json_text.startswith('```json'):
                json_text = json_text[7:-3]
            elif json_text.startswith('```'):
                json_text = json_text[3:-3]
            
            # Parse and return the JSON
            optimized_data = json.loads(json_text)
            return optimized_data
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error in optimization: {e}")
            print(f"Raw response: {json_text}")
            return resume_data  # Return original if optimization fails
        except Exception as e:
            print(f"OpenAI optimization error: {e}")
            return resume_data  # Return original if optimization fails
    
    def _fallback_parse(self):
        """Simple fallback if AI parsing fails"""
        return {
            "personal_info": {"name": "", "email": "", "phone": "", "linkedin": "", "website": "", "github": "", "location": ""},
            "summary": "",
            "skills": [],
            "experience": [],
            "projects": [],
            "education": [],
            "certifications": [],
            "awards": [],
            "languages": [],
            "volunteer": []
        }
    
    def generate_cover_letter(self, resume_data, job_description):
        """Generate a personalized cover letter based on resume and job description"""
        
        # Extract key information from resume
        name = resume_data.get('personal_info', {}).get('name', 'there')
        relevant_experience = []
        
        # Get top 2-3 most relevant experience bullet points
        if resume_data.get('experience'):
            for exp in resume_data['experience'][:2]:  # Top 2 experiences
                if exp.get('bullets'):
                    relevant_experience.extend(exp['bullets'][:2])  # Top 2 bullets each
        
        # Get relevant projects
        relevant_projects = []
        if resume_data.get('projects'):
            for project in resume_data['projects'][:2]:  # Top 2 projects
                if project.get('name'):
                    project_desc = project.get('description', '')
                    if project.get('bullets'):
                        project_desc = project['bullets'][0]  # First bullet point
                    relevant_projects.append(f"{project['name']}: {project_desc}")
        
        # Get key skills
        key_skills = resume_data.get('skills', [])[:8]  # Top 8 skills
        
        prompt = f"""
Write a concise, professional cover letter paragraph (4-6 sentences) for someone applying to this job. The message should be suitable for emailing to a hiring manager or recruiter.

CANDIDATE INFORMATION:
Name: {name}
Key Skills: {', '.join(key_skills)}
Relevant Experience: {' | '.join(relevant_experience[:3])}
Relevant Projects: {' | '.join(relevant_projects)}

JOB DESCRIPTION:
{job_description[:2000]}

REQUIREMENTS:
1. Keep it to ONE paragraph (4-6 sentences maximum)
2. Start with a strong opening that mentions specific interest in the role
3. Highlight 2-3 most relevant qualifications that match the job requirements
4. Include specific technologies/skills mentioned in the job posting
5. End with enthusiasm and a call to action
6. Use a professional but engaging tone
7. Don't use overly formal language - keep it conversational but professional
8. Focus on value the candidate can bring to the company

Write ONLY the paragraph text, no subject line, greeting, or signature.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at writing compelling, concise cover letters that highlight relevant experience and generate interest from hiring managers. You write in a professional but engaging tone."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            # Extract the cover letter text
            cover_letter = response.choices[0].message.content.strip()
            return cover_letter
            
        except Exception as e:
            print(f"Cover letter generation error: {e}")
            return "I'm excited about the opportunity to contribute to your team. My experience and skills align well with the requirements for this position, and I would welcome the chance to discuss how I can add value to your organization. I look forward to hearing from you."

    def answer_application_questions(self, resume_data, job_description, questions):
        """Generate concise answers to application questions based on resume and job description"""
        
        # Extract key information from resume
        name = resume_data.get('personal_info', {}).get('name', 'the candidate')
        
        # Prepare resume summary for context
        resume_summary = {
            'experience': resume_data.get('experience', [])[:3],  # Top 3 experiences
            'skills': resume_data.get('skills', [])[:10],  # Top 10 skills
            'projects': resume_data.get('projects', [])[:3],  # Top 3 projects
            'education': resume_data.get('education', []),
            'summary': resume_data.get('summary', ''),
            'certifications': resume_data.get('certifications', [])
        }
        
        prompt = f"""
You are an expert at answering job application questions concisely and effectively. Answer each question based on the candidate's OPTIMIZED resume (which has been tailored for this specific job) and the job description.

CANDIDATE'S OPTIMIZED RESUME SUMMARY:
{json.dumps(resume_summary, indent=2)}

JOB DESCRIPTION:
{job_description[:2000]}

QUESTIONS TO ANSWER:
{chr(10).join(f"{i+1}. {q}" for i, q in enumerate(questions))}

REQUIREMENTS:
1. Answer each question in 2-4 sentences maximum
2. Base answers on the actual optimized resume content and job requirements
3. Be specific and use concrete examples from the optimized resume when possible
4. Tailor answers to show alignment with the job description
5. Use a professional but personable tone
6. Focus on value the candidate can bring to this specific role
7. Leverage the optimized skills and experience that have been tailored for this job
8. If a question cannot be answered from the resume, provide a reasonable professional response
9. Number each answer to match the question number

Return the answers in this exact format:
1. [Answer to question 1]

2. [Answer to question 2]

3. [Answer to question 3]

etc.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at answering job application questions concisely and effectively based on candidate qualifications and job requirements."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=1500
            )
            
            # Extract the answers
            answers_text = response.choices[0].message.content.strip()
            
            # Parse the numbered answers into a list
            answers = []
            current_answer = ""
            current_number = 1
            
            for line in answers_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                # Check if this line starts with a number
                if line.startswith(f"{current_number}."):
                    # If we have a current answer, save it
                    if current_answer.strip():
                        answers.append(current_answer.strip())
                    
                    # Start new answer (remove the number prefix)
                    current_answer = line[len(f"{current_number}."):]
                    current_number += 1
                else:
                    # Continue the current answer
                    current_answer += " " + line
            
            # Don't forget the last answer
            if current_answer.strip():
                answers.append(current_answer.strip())
            
            # If parsing failed, try a simpler approach
            if len(answers) != len(questions):
                # Split by double newlines or numbered patterns
                import re
                answers = re.split(r'\n\s*\d+\.\s*', answers_text)
                # Remove empty first element if it exists
                answers = [a.strip() for a in answers if a.strip()]
                
                # If still not matching, just return the raw text split by reasonable breaks
                if len(answers) != len(questions):
                    sentences = answers_text.split('. ')
                    answers = []
                    current = ""
                    sentences_per_answer = max(1, len(sentences) // len(questions))
                    
                    for i, sentence in enumerate(sentences):
                        current += sentence + ". "
                        if (i + 1) % sentences_per_answer == 0 or i == len(sentences) - 1:
                            answers.append(current.strip())
                            current = ""
            
            # Ensure we have the right number of answers
            while len(answers) < len(questions):
                answers.append("I believe my experience and skills make me a strong candidate for this position.")
            
            # Trim to match question count
            answers = answers[:len(questions)]
            
            return answers
            
        except Exception as e:
            print(f"Question answering error: {e}")
            # Return default answers
            return ["I believe my experience and skills make me a strong candidate for this position."] * len(questions)

def generate_professional_resume(resume_data, output_path, job_url=""):
    """Generate clean PDF from structured data with clickable links"""
    doc = SimpleDocTemplate(output_path, pagesize=letter, 
                          rightMargin=0.75*inch, leftMargin=0.75*inch,
                          topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    name_style = ParagraphStyle('Name', parent=styles['Heading1'], fontSize=22,
                               spaceAfter=4, alignment=TA_CENTER, textColor=darkblue,
                               fontName='Helvetica-Bold')
    
    contact_style = ParagraphStyle('Contact', parent=styles['Normal'], fontSize=11,
                                  spaceAfter=16, alignment=TA_CENTER, textColor=gray)
    
    section_style = ParagraphStyle('Section', parent=styles['Heading2'], fontSize=13,
                                  spaceAfter=8, spaceBefore=16, textColor=darkblue,
                                  fontName='Helvetica-Bold')
    
    job_style = ParagraphStyle('Job', parent=styles['Normal'], fontSize=12,
                              spaceAfter=4, spaceBefore=8, fontName='Helvetica-Bold')
    
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=11, spaceAfter=6)
    
    bullet_style = ParagraphStyle('Bullet', parent=styles['Normal'], fontSize=10,
                                 spaceAfter=3, leftIndent=20)
    
    story = []
    
    # Job URL - make it clickable if it's a valid URL
    # if job_url:
    #     if job_url.startswith('http'):
    #         clickable_job_url = f'<link href="{job_url}">{job_url}</link>'
    #     else:
    #         clickable_job_url = job_url
    #     story.append(Paragraph(f"Tailored for: {clickable_job_url}", 
    #                           ParagraphStyle('JobUrl', parent=styles['Normal'], fontSize=9,
    #                                        spaceAfter=12, alignment=TA_CENTER, textColor=gray)))
    
    # Header
    personal = resume_data.get('personal_info', {})
    if personal.get('name'):
        story.append(Paragraph(personal['name'], name_style))
    
    # Contact - OpenAI should have cleaned the URLs already
    contact_parts = []
    for field in ['email', 'phone', 'linkedin', 'website', 'github', 'location']:
        if personal.get(field):
            value = personal[field]
            if field == 'email':
                contact_parts.append(f'<link href="mailto:{value}">{value}</link>')
            elif field in ['linkedin', 'website', 'github'] and value.startswith('http'):
                contact_parts.append(f'<link href="{value}">{value}</link>')
            else:
                contact_parts.append(value)
    
    if contact_parts:
        story.append(Paragraph(' • '.join(contact_parts), contact_style))
    
    # Summary
    if resume_data.get('summary'):
        story.append(Paragraph("PROFESSIONAL SUMMARY", section_style))
        story.append(Paragraph(resume_data['summary'], body_style))
    
    # Skills
    if resume_data.get('skills'):
        story.append(Paragraph("TECHNICAL SKILLS", section_style))
        story.append(Paragraph(' • '.join(resume_data['skills']), body_style))
    
    # Experience
    if resume_data.get('experience'):
        story.append(Paragraph("PROFESSIONAL EXPERIENCE", section_style))
        for job in resume_data['experience']:
            job_line = f"<b>{job.get('title', '')}</b>"
            if job.get('company'):
                job_line += f" | {job['company']}"
            if job.get('location'):
                job_line += f" | {job['location']}"
            if job.get('dates'):
                job_line += f" | {job['dates']}"
            
            story.append(Paragraph(job_line, job_style))
            
            # Include ALL bullet points
            for bullet in job.get('bullets', []):
                story.append(Paragraph(f"• {bullet}", bullet_style))
    
    # Projects - handle both bullets and descriptions
    if resume_data.get('projects'):
        story.append(Paragraph("PROJECTS", section_style))
        for project in resume_data['projects']:
            project_line = f"<b>{project.get('name', '')}</b>"
            if project.get('dates'):
                project_line += f" | {project['dates']}"
            if project.get('url') and project['url'].startswith('http'):
                project_line += f" | <link href=\"{project['url']}\">{project['url']}</link>"
            elif project.get('url'):
                project_line += f" | {project['url']}"
            
            story.append(Paragraph(project_line, job_style))
            
            # Check if project has bullet points or just description
            if project.get('bullets'):
                # Project has bullet points - use them
                for bullet in project['bullets']:
                    story.append(Paragraph(f"• {bullet}", bullet_style))
            elif project.get('description'):
                # Project has description paragraph - display as body text
                story.append(Paragraph(project['description'], body_style))
            
            # Add technologies
            if project.get('technologies'):
                tech_text = f"Technologies: {', '.join(project['technologies'])}"
                story.append(Paragraph(tech_text, bullet_style))
    
    # Education
    if resume_data.get('education'):
        story.append(Paragraph("EDUCATION", section_style))
        for edu in resume_data['education']:
            edu_line = f"<b>{edu.get('degree', '')}</b>"
            if edu.get('school'):
                edu_line += f" | {edu['school']}"
            if edu.get('location'):
                edu_line += f" | {edu['location']}"
            if edu.get('date'):
                edu_line += f" | {edu['date']}"
            
            story.append(Paragraph(edu_line, body_style))
            
            # Add additional education details
            if edu.get('gpa'):
                story.append(Paragraph(f"GPA: {edu['gpa']}", bullet_style))
            if edu.get('honors'):
                story.append(Paragraph(f"Honors: {edu['honors']}", bullet_style))
            if edu.get('relevant_courses'):
                courses_text = f"Relevant Courses: {', '.join(edu['relevant_courses'])}"
                story.append(Paragraph(courses_text, bullet_style))
    
    # Certifications
    if resume_data.get('certifications'):
        story.append(Paragraph("CERTIFICATIONS", section_style))
        for cert in resume_data['certifications']:
            story.append(Paragraph(f"• {cert}", bullet_style))
    
    # Awards
    if resume_data.get('awards'):
        story.append(Paragraph("AWARDS & ACHIEVEMENTS", section_style))
        for award in resume_data['awards']:
            story.append(Paragraph(f"• {award}", bullet_style))
    
    # Languages
    if resume_data.get('languages'):
        story.append(Paragraph("LANGUAGES", section_style))
        story.append(Paragraph(' • '.join(resume_data['languages']), body_style))
    
    # Volunteer Experience
    if resume_data.get('volunteer'):
        story.append(Paragraph("VOLUNTEER EXPERIENCE", section_style))
        for vol in resume_data['volunteer']:
            vol_line = f"<b>{vol.get('role', '')}</b>"
            if vol.get('organization'):
                vol_line += f" | {vol['organization']}"
            if vol.get('dates'):
                vol_line += f" | {vol['dates']}"
            
            story.append(Paragraph(vol_line, job_style))
            
            if vol.get('description'):
                story.append(Paragraph(f"• {vol['description']}", bullet_style))
    
    doc.build(story)
    return output_path

def generate_cover_letter_pdf(resume_data, cover_letter_text, output_path, job_url=""):
    """Generate a professionally formatted cover letter PDF"""
    doc = SimpleDocTemplate(output_path, pagesize=letter, 
                          rightMargin=1*inch, leftMargin=1*inch,
                          topMargin=1*inch, bottomMargin=1*inch)
    
    styles = getSampleStyleSheet()
    
    # Custom styles for cover letter
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=11,
                                 spaceAfter=12, alignment=TA_LEFT, fontName='Helvetica')
    
    date_style = ParagraphStyle('Date', parent=styles['Normal'], fontSize=11,
                               spaceAfter=24, alignment=TA_LEFT, fontName='Helvetica')
    
    greeting_style = ParagraphStyle('Greeting', parent=styles['Normal'], fontSize=11,
                                   spaceAfter=18, alignment=TA_LEFT, fontName='Helvetica')
    
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=11,
                               spaceAfter=18, alignment=TA_LEFT, fontName='Helvetica',
                               leading=22)  # Double spacing equivalent
    
    closing_style = ParagraphStyle('Closing', parent=styles['Normal'], fontSize=11,
                                  spaceAfter=36, alignment=TA_LEFT, fontName='Helvetica')
    
    signature_style = ParagraphStyle('Signature', parent=styles['Normal'], fontSize=11,
                                    alignment=TA_LEFT, fontName='Helvetica')
    
    story = []
    
    # Header with personal info
    personal = resume_data.get('personal_info', {})
    if personal.get('name'):
        story.append(Paragraph(f"<b>{personal['name']}</b>", header_style))
    
    # Contact info
    contact_parts = []
    if personal.get('email'):
        contact_parts.append(personal['email'])
    if personal.get('phone'):
        contact_parts.append(personal['phone'])
    if personal.get('location'):
        contact_parts.append(personal['location'])
    
    if contact_parts:
        story.append(Paragraph(' | '.join(contact_parts), header_style))
    
    # Add space after header
    story.append(Spacer(1, 24))
    
    # Date
    from datetime import datetime
    current_date = datetime.now().strftime("%B %d, %Y")
    story.append(Paragraph(current_date, date_style))
    
    # Greeting
    story.append(Paragraph("Dear Hiring Manager,", greeting_style))
    
    # Main cover letter content
    story.append(Paragraph(cover_letter_text, body_style))
    
    # Closing
    story.append(Paragraph("Thank you for your time and consideration. I look forward to hearing from you.", body_style))
    story.append(Paragraph("Sincerely,", closing_style))
    
    # Signature
    if personal.get('name'):
        story.append(Paragraph(personal['name'], signature_style))
    
    doc.build(story)
    return output_path

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process-resume', methods=['POST'])
def process_resume():
    if 'resume' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'}), 400
    
    resume_file = request.files['resume']
    job_url = request.form.get('job_url', '')
    creativity_level = float(request.form.get('creativity', 0.5))  # Default 0.5
    
    if resume_file.filename == '' or job_url == '':
        return jsonify({'success': False, 'error': 'Missing file or job URL'}), 400
    
    try:
        # Read file content
        filename = secure_filename(resume_file.filename)
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext == '.txt':
            content = resume_file.read().decode('utf-8')
        elif file_ext == '.pdf':
            import PyPDF2
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{filename}")
            resume_file.save(temp_path)
            
            with open(temp_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                content = ""
                for page in reader.pages:
                    content += page.extract_text() + "\n"
            
            os.remove(temp_path)
        else:
            return jsonify({'success': False, 'error': 'Unsupported file type'}), 400
        
        # Scrape job description
        scraper = JobScraper()
        job_description = scraper.scrape_job_description(job_url)
        
        if not job_description:
            return jsonify({'success': False, 'error': 'Could not scrape job description from the provided URL. Please check the URL and try again.'}), 400
        
        # Parse resume with AI
        ai_parser = AIResumeParser(openai_client)
        structured_data = ai_parser.parse_resume_with_ai(content)
        
        # Optimize resume based on job description
        optimized_data = ai_parser.optimize_resume_for_job(
            structured_data, 
            job_description, 
            creativity_level
        )
        
        # Cache both original and optimized versions
        cache_key = hashlib.md5((content + job_url + str(creativity_level)).encode()).hexdigest()
        cache_file = os.path.join(app.config['CACHE_FOLDER'], f"{cache_key}.json")
        with open(cache_file, 'w') as f:
            json.dump({
                'original': structured_data,
                'optimized': optimized_data,
                'job_description': job_description[:1000],  # Store truncated version
                'job_url': job_url,
                'creativity_level': creativity_level
            }, f, indent=2)
        
        # Generate personalized PDF filename
        user_name = optimized_data.get('personal_info', {}).get('name', '')
        safe_name = create_safe_filename(user_name, 'Resume')
        output_filename = f"{safe_name}_Resume.pdf"
        
        # Ensure filename is unique by adding cache key if file exists
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        if os.path.exists(output_path):
            output_filename = f"{safe_name}_Resume_{cache_key[:8]}.pdf"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        
        generate_professional_resume(optimized_data, output_path, job_url)
        
        return jsonify({
            'success': True,
            'message': 'Resume optimized successfully',
            'cache_key': cache_key,
            'original_data': structured_data,
            'optimized_data': optimized_data,
            'job_description_preview': job_description[:500] + "..." if len(job_description) > 500 else job_description,
            'download_url': f"/download/{output_filename}",
            'file_type': 'pdf'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/api/download-edited-resume', methods=['POST'])
def download_edited_resume():
    try:
        data = request.get_json()
        cache_key = data.get('cache_key')
        
        if not cache_key:
            return jsonify({'success': False, 'error': 'Missing cache key'}), 400
        
        # Load cache data to get the edited resume
        cache_file = os.path.join(app.config['CACHE_FOLDER'], f"{cache_key}.json")
        
        if not os.path.exists(cache_file):
            return jsonify({'success': False, 'error': 'Cache file not found'}), 404
        
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        
        # Use edited data if available, otherwise fall back to optimized
        resume_data = cache_data.get('edited', cache_data.get('optimized'))
        job_url = cache_data.get('job_url', '')
        
        if not resume_data:
            return jsonify({'success': False, 'error': 'No resume data found in cache'}), 400
        
        # Generate personalized PDF filename
        user_name = resume_data.get('personal_info', {}).get('name', '')
        safe_name = create_safe_filename(user_name, 'Resume')
        output_filename = f"{safe_name}_Resume_Edited.pdf"
        
        # Ensure filename is unique by adding timestamp if file exists
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        if os.path.exists(output_path):
            timestamp = str(int(time.time()))[-6:]
            output_filename = f"{safe_name}_Resume_Edited_{timestamp}.pdf"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        
        # Generate the resume PDF with edited data
        generate_professional_resume(resume_data, output_path, job_url)
        
        # Return the PDF file
        return send_from_directory(app.config['UPLOAD_FOLDER'], output_filename, 
                                 as_attachment=True, download_name=output_filename)
        
    except Exception as e:
        print(f"Download edited resume error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-cover-letter', methods=['POST'])
def generate_cover_letter():
    try:
        data = request.get_json()
        resume_data = data.get('resume_data')
        job_url = data.get('job_url')
        
        if not resume_data or not job_url:
            return jsonify({'success': False, 'error': 'Missing resume data or job URL'}), 400
        
        # Scrape job description (reuse existing scraper)
        scraper = JobScraper()
        job_description = scraper.scrape_job_description(job_url)
        
        if not job_description:
            return jsonify({'success': False, 'error': 'Could not scrape job description'}), 400
        
        # Generate cover letter using AI
        ai_parser = AIResumeParser(openai_client)
        cover_letter = ai_parser.generate_cover_letter(resume_data, job_description)
        
        return jsonify({
            'success': True,
            'cover_letter': cover_letter
        })
        
    except Exception as e:
        print(f"Cover letter generation error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/answer-questions', methods=['POST'])
def answer_questions():
    try:
        data = request.get_json()
        resume_data = data.get('resume_data')
        job_url = data.get('job_url')
        questions = data.get('questions', '')
        
        if not resume_data or not job_url or not questions.strip():
            return jsonify({'success': False, 'error': 'Missing resume data, job URL, or questions'}), 400
        
        # Split questions by line breaks and filter out empty lines
        question_list = [q.strip() for q in questions.split('\n') if q.strip()]
        
        if not question_list:
            return jsonify({'success': False, 'error': 'No valid questions found'}), 400
        
        # Scrape job description (reuse existing scraper)
        scraper = JobScraper()
        job_description = scraper.scrape_job_description(job_url)
        
        if not job_description:
            return jsonify({'success': False, 'error': 'Could not scrape job description'}), 400
        
        # Generate answers using AI
        ai_parser = AIResumeParser(openai_client)
        answers = ai_parser.answer_application_questions(resume_data, job_description, question_list)
        
        return jsonify({
            'success': True,
            'answers': answers
        })
        
    except Exception as e:
        print(f"Question answering error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/download-cover-letter', methods=['POST'])
def download_cover_letter():
    try:
        data = request.get_json()
        resume_data = data.get('resume_data')
        job_url = data.get('job_url')
        cover_letter_text = data.get('cover_letter_text')
        
        if not resume_data or not cover_letter_text:
            return jsonify({'success': False, 'error': 'Missing resume data or cover letter text'}), 400
        
        # Generate personalized PDF filename
        user_name = resume_data.get('personal_info', {}).get('name', '')
        safe_name = create_safe_filename(user_name, 'CoverLetter')
        output_filename = f"{safe_name}_Cover_Letter.pdf"
        
        # Ensure filename is unique by adding timestamp if file exists
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        if os.path.exists(output_path):
            import time
            timestamp = str(int(time.time()))[-6:]  # Last 6 digits of timestamp
            output_filename = f"{safe_name}_Cover_Letter_{timestamp}.pdf"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        
        # Generate the cover letter PDF
        generate_cover_letter_pdf(resume_data, cover_letter_text, output_path, job_url)
        
        # Return the PDF file
        return send_from_directory(app.config['UPLOAD_FOLDER'], output_filename, 
                                 as_attachment=True, download_name=output_filename)
        
    except Exception as e:
        print(f"Cover letter download error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/save-edited-resume', methods=['POST'])
def save_edited_resume():
    try:
        data = request.get_json()
        edited_data = data.get('edited_data')
        job_url = data.get('job_url')
        cache_key = data.get('cache_key')
        
        if not edited_data:
            return jsonify({'success': False, 'error': 'Missing edited resume data'}), 400
        
        # Generate cache key if not provided
        if not cache_key:
            content = str(edited_data) + job_url
            cache_key = hashlib.md5(content.encode()).hexdigest()
        
        # Update the cache file with edited data
        cache_file = os.path.join(app.config['CACHE_FOLDER'], f"{cache_key}.json")
        
        if os.path.exists(cache_file):
            # Load existing cache and update with edited data
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            cache_data['edited'] = edited_data
            cache_data['last_edited'] = int(time.time())  # Add timestamp
            
            # Save updated cache
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        else:
            # Create new cache file with edited data
            cache_data = {
                'edited': edited_data,
                'job_url': job_url,
                'last_edited': int(time.time())
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'Resume changes saved successfully',
            'cache_key': cache_key
        })
        
    except Exception as e:
        print(f"Save edited resume error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)