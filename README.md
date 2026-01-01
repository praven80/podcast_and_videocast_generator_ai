# DocTalk - AI-Powered Document-to-Podcast Converter

DocTalk is an innovative application that transforms documents and web articles into engaging podcast-style conversations using AWS Bedrock and Amazon Polly. It supports both audio and video output formats with AI-generated visuals.

You can view a short demo video in the "Demo" folder.

## Features

### Input Sources
- Document Upload (PDF, DOCX, TXT)
- Web Articles (via URL)
- Existing Scripts (TXT)

### Output Formats
- Audio Podcasts
- Video Podcasts with AI-Generated Visuals

### Key Capabilities
- Natural conversation generation between two hosts
- Dynamic voice synthesis using Amazon Polly
- AI-powered image generation for video content
- Support for multiple input formats
- Real-time content processing
- Custom prompt support for content curation

## Architecture

- Frontend: Streamlit
- Backend Services:
  - Amazon Bedrock for AI processing
  - Amazon Polly for voice synthesis
  - AWS ECS (Fargate) for deployment
  - Application Load Balancer for traffic distribution

## Prerequisites

- AWS Account with appropriate permissions
- Python 3.11+
- Docker
- AWS CDK

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd doctalk
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure AWS credentials:
```bash
aws configure
```

## Local Development

1. Run the Streamlit application:
```bash
streamlit run app.py
```

2. Access the application at:
```
http://localhost:8501
```

## Deployment

### Using AWS CDK

1. Install AWS CDK:
```bash
npm install -g aws-cdk
```

2. Bootstrap CDK (first time only):
```bash
cdk bootstrap
```

3. Deploy the stack:
```bash
cdk deploy
```

## Docker Support

Build the container:
```bash
docker build -t doctalk .
```

Run locally:
```bash
docker run -p 8501:8501 doctalk
```

## Usage

1. Select input source:
   - Upload document
   - Enter website URL
   - Upload existing script

2. Choose output format:
   - Audio
   - Video

3. (Optional) Enter custom prompts to customize content

4. Click "Launch DocTalk" to generate content

## Infrastructure

The application is deployed with:
- VPC with public/private subnets
- ECS Fargate cluster
- Application Load Balancer
- Auto-scaling capabilities
- Health checks and monitoring

## Security

- Private subnets for container deployment
- Security groups for network access control
- IAM roles with least privilege
- VPC isolation

## Environment Variables

Required environment variables:
```
AWS_REGION=<your-region>
```