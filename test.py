from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import black, darkblue, gray
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch
import json

def generate_professional_resume(resume_data, output_path):
    """
    Takes structured resume data and generates a clean PDF
    
    resume_data should look like:
    {
        "personal_info": {"name": "John Doe", "email": "john@email.com", "phone": "555-1234"},
        "summary": "Brief professional summary...",
        "experience": [
            {
                "title": "Software Engineer",
                "company": "Tech Corp",
                "dates": "2020-2023",
                "bullets": ["Did this", "Accomplished that"]
            }
        ],
        "skills": ["Python", "React", "SQL"],
        "education": [
            {
                "degree": "BS Computer Science",
                "school": "State University",
                "date": "2020"
            }
        ]
    }
    """
    
    # Create document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Define styles
    styles = getSampleStyleSheet()
    
    # Custom styles for clean look
    name_style = ParagraphStyle(
        'NameStyle',
        parent=styles['Heading1'],
        fontSize=22,
        spaceAfter=4,
        alignment=TA_CENTER,
        textColor=darkblue,
        fontName='Helvetica-Bold'
    )
    
    contact_style = ParagraphStyle(
        'ContactStyle',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=16,
        alignment=TA_CENTER,
        fontName='Helvetica',
        textColor=gray
    )
    
    section_header_style = ParagraphStyle(
        'SectionHeaderStyle',
        parent=styles['Heading2'],
        fontSize=13,
        spaceAfter=8,
        spaceBefore=16,
        textColor=darkblue,
        fontName='Helvetica-Bold',
        borderWidth=1,
        borderColor=darkblue,
        borderPadding=4
    )
    
    job_header_style = ParagraphStyle(
        'JobHeaderStyle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=4,
        spaceBefore=8,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        fontName='Helvetica'
    )
    
    bullet_style = ParagraphStyle(
        'BulletStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=3,
        leftIndent=20,
        fontName='Helvetica'
    )
    
    # Build the document content
    story = []
    
    # === HEADER SECTION ===
    personal = resume_data.get('personal_info', {})
    
    # Name
    if personal.get('name'):
        story.append(Paragraph(personal['name'], name_style))
    
    # Contact info in one line
    contact_parts = []
    if personal.get('email'):
        contact_parts.append(personal['email'])
    if personal.get('phone'):
        contact_parts.append(personal['phone'])
    if personal.get('linkedin'):
        contact_parts.append(personal['linkedin'])
    
    if contact_parts:
        contact_line = " • ".join(contact_parts)
        story.append(Paragraph(contact_line, contact_style))
    
    # === SUMMARY SECTION ===
    if resume_data.get('summary'):
        story.append(Paragraph("PROFESSIONAL SUMMARY", section_header_style))
        story.append(Paragraph(resume_data['summary'], body_style))
    
    # === SKILLS SECTION ===
    if resume_data.get('skills'):
        story.append(Paragraph("TECHNICAL SKILLS", section_header_style))
        skills_text = " • ".join(resume_data['skills'])
        story.append(Paragraph(skills_text, body_style))
    
    # === EXPERIENCE SECTION ===
    if resume_data.get('experience'):
        story.append(Paragraph("PROFESSIONAL EXPERIENCE", section_header_style))
        
        for job in resume_data['experience']:
            # Job title, company, dates
            job_line = f"<b>{job.get('title', '')}</b>"
            if job.get('company'):
                job_line += f" | {job['company']}"
            if job.get('dates'):
                job_line += f" | {job['dates']}"
            
            story.append(Paragraph(job_line, job_header_style))
            
            # Job description bullets
            if job.get('bullets'):
                for bullet in job['bullets']:
                    story.append(Paragraph(f"• {bullet}", bullet_style))
    
    # === EDUCATION SECTION ===
    if resume_data.get('education'):
        story.append(Paragraph("EDUCATION", section_header_style))
        
        for edu in resume_data['education']:
            edu_line = f"<b>{edu.get('degree', '')}</b>"
            if edu.get('school'):
                edu_line += f" | {edu['school']}"
            if edu.get('date'):
                edu_line += f" | {edu['date']}"
            
            story.append(Paragraph(edu_line, body_style))
    
    # Generate the PDF
    doc.build(story)
    return output_path

# Example usage
def test_resume_generator():
    # Sample structured data
    sample_data = {
        "personal_info": {
            "name": "Jane Smith",
            "email": "jane.smith@email.com",
            "phone": "(555) 123-4567",
            "linkedin": "linkedin.com/in/janesmith"
        },
        "summary": "Experienced software engineer with 5+ years developing scalable web applications. Proven track record of leading cross-functional teams and delivering high-impact projects on time.",
        "skills": [
            "Python", "JavaScript", "React", "Node.js", "SQL", "AWS", "Docker", "Git"
        ],
        "experience": [
            {
                "title": "Senior Software Engineer",
                "company": "Tech Innovations Inc.",
                "dates": "2021 - Present",
                "bullets": [
                    "Led development of microservices architecture serving 1M+ daily users",
                    "Mentored 3 junior developers and improved team productivity by 25%",
                    "Implemented CI/CD pipelines reducing deployment time from 2 hours to 15 minutes"
                ]
            },
            {
                "title": "Software Engineer",
                "company": "StartupCorp",
                "dates": "2019 - 2021",
                "bullets": [
                    "Built responsive web applications using React and Node.js",
                    "Collaborated with design team to implement pixel-perfect UI components",
                    "Optimized database queries resulting in 40% faster page load times"
                ]
            }
        ],
        "education": [
            {
                "degree": "Bachelor of Science in Computer Science",
                "school": "State University",
                "date": "2019"
            }
        ]
    }
    
    generate_professional_resume(sample_data, "sample_resume.pdf")
    print("Resume generated: sample_resume.pdf")

if __name__ == "__main__":
    test_resume_generator()