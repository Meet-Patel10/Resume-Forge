"""Test the LaTeX engine with mock data — no API tokens needed."""

from app.services.latex_engine import render_latex

# Mock resume data matching the exact JSON schema the AI would return
mock_resume = {
    "header": {
        "name": "Meet Patel",
        "location": "Halifax, NS",
        "phone": None,
        "email": "meett.patel.2803@gmail.com",
        "linkedin": None,
        "github": None,
        "tagline": "PGWP-eligible | Available for full-time roles"
    },
    "summary": "Full Stack Developer with 3 years of industry experience. Currently, pursuing a Master's in Applied Computer Science from St. Francis Xavier University. Professional background includes working on connected-vehicle systems for major automotive clients like BMW. There, I worked mainly with Java and database management using PostgreSQL. Have strong academic performance in Machine Learning and Embedded systems as well.",
    "skills": [
        {
            "category": "Languages & Frameworks",
            "items": ["Java", "Python", "C++", "Vue.js", "Spring Boot", "Microservices", "RESTful APIs", "PostgreSQL"]
        },
        {
            "category": "Tools & Concepts",
            "items": ["Git", "Docker", "SimulIDE", "FSM", "Real-Time Systems (EDF/RMS)", "IoT", "SDN", "Machine Learning (PEFT)"]
        }
    ],
    "projects": [
        {
            "name": "BiomedCLIP Integration for Medical Imaging (Ongoing)",
            "tech_stack": "Python, PyTorch, Transformers",
            "bullets": [
                "Implementing BiomedCLIP within the DeepTune software to enable multimodal learning for medical imaging datasets.",
                "Developing fine-tuning and evaluation pipelines to adapt pretrained vision-language models for domain-specific clinical image analysis."
            ]
        },
        {
            "name": "Automated Parking Assistance System",
            "tech_stack": "C++, Arduino, SimulIDE 1.1.0, FSM",
            "bullets": [
                "Designed an automotive parking assistance system using a Finite State Machine (FSM) with hysteresis to ensure stable transitions between Searching, Aligning, and Parked states.",
                "Implemented non-blocking scheduling and interrupt-driven sensing to improve real-time responsiveness."
            ]
        },
        {
            "name": "Satellite Communication Optimization",
            "tech_stack": "Python, Real-Time Scheduling (EDF, RMS, LST)",
            "bullets": [
                "Optimized satellite communication for emergency scenarios using Real-Time Systems (RTS) principles.",
                "Implemented EDF, RMS, and LST scheduling algorithms and message segmentation logic to prioritize critical sporadic tasks."
            ]
        }
    ],
    "experience": [
        {
            "title": "Java Full Stack Developer",
            "company": "Capgemini India",
            "location": "Mumbai, India",
            "dates": "Feb 2022 -- March 2024",
            "bullets": [
                "Worked directly within the XTECH engagement for BMW to maintain backend systems that connect new vehicles to the network, ensuring seamless data flow for app development and provisioning teams.",
                "Acted as a technical link between the App Development, Provisioning, and Software Database teams to resolve integration issues, ensuring that online systems for connected cars remained stable and responsive."
            ]
        },
        {
            "title": "Jr. Front-End Developer",
            "company": "Alian Software",
            "location": "Anand, India",
            "dates": "Jan 2021 -- Nov 2021",
            "bullets": [
                "Designed and coded creative, interactive user interfaces for four distinct web projects, focusing heavily on delivering a smooth and intuitive user experience."
            ]
        }
    ],
    "education": [
        {
            "degree": "Master of Applied Computer Science",
            "school": "St. Francis Xavier University",
            "location": "NS",
            "dates": "2024 -- Present",
            "details": "GPA: 4.0 (87.0%) | Specialization: Machine Learning Design, Real-Time Systems, Embedded Systems, Computational Logic, Computer Network System, and Software Design."
        },
        {
            "degree": "B.Tech in Computer Science Engineering",
            "school": "SRM Institute of Science & Technology",
            "location": "India",
            "dates": "2017 -- 2021",
            "details": "CGPA: 8.9 | Coursework: Data Structures, Algorithms (ADA), Operating Systems, OOAD, DBMS, Operating Systems, and Artificial Intelligence."
        }
    ],
    "other_experience": [
        {
            "title": "Front Desk Representative",
            "company": "Maritime Inn",
            "location": "Antigonish, NS",
            "dates": "Jan 2025 -- Present",
            "bullets": [
                "Manage front desk operations, financial reconciliation, and guest relations while maintaining full-time academic status."
            ]
        },
        {
            "title": "Night Shuttle Driver",
            "company": "DriveU (Student Union)",
            "location": "Antigonish, NS",
            "dates": "Sept 2025 -- Present",
            "bullets": [
                "Safely drop university students to their homes during night, ensuring everyone returns safely."
            ]
        }
    ],
    "other": {
        "additional": None,
        "languages": "English (Advanced) | Hindi (Advanced) | Gujarati (Native)"
    },
    "keywords_used": ["Java", "Spring Boot", "PostgreSQL", "Microservices", "RESTful APIs", "Docker", "Git"]
}

# Generate LaTeX
latex_output = render_latex(mock_resume)

# Print to console
print("=" * 80)
print("GENERATED LaTeX OUTPUT")
print("=" * 80)
print(latex_output)
print("=" * 80)

# Also save to file for easy viewing
with open("test_output.tex", "w") as f:
    f.write(latex_output)

print(f"\nSaved to test_output.tex ({len(latex_output)} chars)")
print("You can paste this into Overleaf (https://www.overleaf.com) to see the PDF.")
