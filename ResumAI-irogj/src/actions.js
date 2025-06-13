import OpenAI from 'openai';
import fs from 'fs';
import path from 'path';
import mammoth from 'mammoth';
import { v4 as uuidv4 } from 'uuid';
import { jsPDF } from 'jspdf';
import { HttpError } from 'wasp/server';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

export const uploadResumeFile = async (args, context) => {
  if (!context.user) {
    throw new HttpError(401, 'User not authenticated');
  }
  
  const { filename, originalName, jobUrl } = args;
  
  // Create resume record
  const resume = await context.entities.Resume.create({
    data: {
      fileName: originalName,
      filePath: filename,
      jobUrl: jobUrl || null,
      userId: context.user.id
    }
  });
  
  return resume;
};

export const processResumeWithAI = async (args, context) => {
  if (!context.user) {
    throw new HttpError(401, 'User not authenticated');
  }
  
  // Check user credits
  const user = await context.entities.User.findUnique({
    where: { id: context.user.id }
  });
  
  if (user.credits <= 0) {
    throw new HttpError(400, 'Insufficient credits. Please purchase more credits.');
  }
  
  const { resumeId, jobUrl } = args;
  
  const resume = await context.entities.Resume.findUnique({
    where: { id: resumeId, userId: context.user.id }
  });
  
  if (!resume) {
    throw new HttpError(404, 'Resume not found');
  }
  
  try {
    // Read and parse the resume file
    const filePath = path.join('uploads', resume.filePath);
    const fileContent = await extractTextFromFile(filePath, resume.fileName);
    
    // Process with OpenAI
    const structuredData = await parseResumeWithAI(fileContent);
    
    // Generate processed resume
    const processedFileName = `processed_${uuidv4()}.pdf`;
    const processedPath = path.join('uploads', processedFileName);
    await generateProfessionalResume(structuredData, processedPath, jobUrl);
    
    // Update resume record
    const updatedResume = await context.entities.Resume.update({
      where: { id: resumeId },
      data: {
        processedPath: processedFileName,
        jobUrl: jobUrl,
        structuredData: structuredData
      }
    });
    
    // Deduct credit
    await context.entities.User.update({
      where: { id: context.user.id },
      data: { credits: { decrement: 1 } }
    });
    
    return {
      success: true,
      resume: updatedResume,
      downloadUrl: `/uploads/${processedFileName}`
    };
    
  } catch (error) {
    console.error('Error processing resume:', error);
    throw new HttpError(500, 'Failed to process resume: ' + error.message);
  }
};

async function extractTextFromFile(filePath, fileName) {
  const ext = path.extname(fileName).toLowerCase();
  
  if (ext === '.txt') {
    return fs.readFileSync(filePath, 'utf8');
  } else if (ext === '.docx' || ext === '.doc') {
    const buffer = fs.readFileSync(filePath);
    const result = await mammoth.extractRawText({ buffer });
    return result.value;
  } else if (ext === '.pdf') {
    // For PDF, we'll use a simple text extraction
    // You might want to add pdf-parse library for better extraction
    return "PDF content extraction needs pdf-parse library";
  }
  
  throw new Error('Unsupported file type');
}

async function parseResumeWithAI(resumeText) {
  const prompt = `
Parse the following resume text into a comprehensive JSON structure. Extract ALL information accurately and include everything present in the resume.

Resume text:
${resumeText}

Please return ONLY a valid JSON object with this structure:
{
    "personal_info": {
        "name": "Full name",
        "email": "email@example.com", 
        "phone": "phone number",
        "linkedin": "LinkedIn URL",
        "website": "personal website URL",
        "github": "GitHub profile URL",
        "location": "city, state if present"
    },
    "summary": "Complete professional summary or objective (if present)",
    "skills": ["skill1", "skill2", "skill3"],
    "experience": [
        {
            "title": "Job title",
            "company": "Company name",
            "location": "Job location if mentioned",
            "dates": "Complete date range",
            "bullets": ["Include ALL bullet points and achievements"]
        }
    ],
    "projects": [
        {
            "name": "Project name",
            "description": "Project description",
            "bullets": ["bullet point 1", "bullet point 2"],
            "technologies": ["tech1", "tech2"],
            "url": "project URL",
            "dates": "project dates if present"
        }
    ],
    "education": [
        {
            "degree": "Complete degree name",
            "school": "Full institution name", 
            "location": "school location if present",
            "date": "graduation date",
            "gpa": "GPA if mentioned",
            "honors": "honors/distinctions if mentioned",
            "relevant_courses": ["course1", "course2"] 
        }
    ],
    "certifications": ["cert1", "cert2"],
    "awards": ["award1", "award2"],
    "languages": ["language1", "language2"],
    "volunteer": [
        {
            "role": "volunteer role",
            "organization": "organization name",
            "dates": "volunteer dates",
            "description": "what they did"
        }
    ]
}

Return only the JSON, no other text.
`;
  
  try {
    const response = await openai.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [
        {
          role: "system",
          content: "You are a comprehensive resume parsing expert. Extract ALL information from resumes into complete JSON format."
        },
        {
          role: "user",
          content: prompt
        }
      ],
      temperature: 0.1,
      max_tokens: 4000
    });
    
    let jsonText = response.choices[0].message.content.trim();
    
    if (jsonText.startsWith('```json')) {
      jsonText = jsonText.slice(7, -3);
    } else if (jsonText.startsWith('```')) {
      jsonText = jsonText.slice(3, -3);
    }
    
    return JSON.parse(jsonText);
    
  } catch (error) {
    console.error('AI parsing error:', error);
    return getDefaultResumeStructure();
  }
}

async function generateProfessionalResume(resumeData, outputPath, jobUrl) {
  const doc = new jsPDF();
  
  let yPosition = 20;
  
  // Add job URL if provided
  if (jobUrl) {
    doc.setFontSize(10);
    doc.text(`Application for: ${jobUrl}`, 20, yPosition);
    yPosition += 10;
  }
  
  // Header
  if (resumeData.personal_info?.name) {
    doc.setFontSize(20);
    doc.text(resumeData.personal_info.name, 20, yPosition);
    yPosition += 15;
  }
  
  // Contact info
  const contact = resumeData.personal_info || {};
  const contactInfo = [contact.email, contact.phone, contact.linkedin, contact.location]
    .filter(Boolean)
    .join(' • ');
  
  if (contactInfo) {
    doc.setFontSize(10);
    doc.text(contactInfo, 20, yPosition);
    yPosition += 15;
  }
  
  // Summary
  if (resumeData.summary) {
    doc.setFontSize(12);
    doc.text('PROFESSIONAL SUMMARY', 20, yPosition);
    yPosition += 8;
    doc.setFontSize(10);
    const summaryLines = doc.splitTextToSize(resumeData.summary, 170);
    doc.text(summaryLines, 20, yPosition);
    yPosition += summaryLines.length * 5 + 10;
  }
  
  // Skills
  if (resumeData.skills?.length) {
    doc.setFontSize(12);
    doc.text('TECHNICAL SKILLS', 20, yPosition);
    yPosition += 8;
    doc.setFontSize(10);
    const skillsText = resumeData.skills.join(' • ');
    const skillsLines = doc.splitTextToSize(skillsText, 170);
    doc.text(skillsLines, 20, yPosition);
    yPosition += skillsLines.length * 5 + 10;
  }
  
  // Experience
  if (resumeData.experience?.length) {
    doc.setFontSize(12);
    doc.text('PROFESSIONAL EXPERIENCE', 20, yPosition);
    yPosition += 8;
    
    resumeData.experience.forEach(job => {
      doc.setFontSize(10);
      const jobTitle = `${job.title || ''} | ${job.company || ''} | ${job.dates || ''}`;
      doc.text(jobTitle, 20, yPosition);
      yPosition += 6;
      
      job.bullets?.forEach(bullet => {
        const bulletLines = doc.splitTextToSize(`• ${bullet}`, 170);
        doc.text(bulletLines, 25, yPosition);
        yPosition += bulletLines.length * 5;
      });
      
      yPosition += 5;
    });
  }
  
  // Save the PDF
  fs.writeFileSync(outputPath, Buffer.from(doc.output('arraybuffer')));
}

function getDefaultResumeStructure() {
  return {
    personal_info: { name: "", email: "", phone: "", linkedin: "", website: "", github: "", location: "" },
    summary: "",
    skills: [],
    experience: [],
    projects: [],
    education: [],
    certifications: [],
    awards: [],
    languages: [],
    volunteer: []
  };
}

export const downloadProcessedResume = async (args, context) => {
  if (!context.user) {
    throw new HttpError(401, 'User not authenticated');
  }
  
  const { resumeId } = args;
  
  const resume = await context.entities.Resume.findUnique({
    where: { id: resumeId, userId: context.user.id }
  });
  
  if (!resume || !resume.processedPath) {
    throw new HttpError(404, 'Processed resume not found');
  }
  
  return {
    downloadUrl: `/uploads/${resume.processedPath}`,
    fileName: `tailored_${resume.fileName}`
  };
};

export const processPayment = async (args, context) => {
  if (!context.user) {
    throw new HttpError(401, 'User not authenticated');
  }
  
  const { amount } = args;
  
  // Simple payment processing (you would integrate with Stripe here)
  const payment = await context.entities.Payment.create({
    data: {
      amount: amount,
      userId: context.user.id
    }
  });
  
  // Add credits based on payment amount (e.g., $5 = 5 credits)
  const creditsToAdd = Math.floor(amount);
  
  await context.entities.User.update({
    where: { id: context.user.id },
    data: { credits: { increment: creditsToAdd } }
  });
  
  return { success: true, creditsAdded: creditsToAdd };
};