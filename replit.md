# Nova AI Chatbot

## Overview

Nova is a Flask-based AI chatbot application powered by Groq's LLM API. The chatbot has a custom personality designed to be friendly and casual, with the ability to switch to a more serious tone for educational or factual queries. The application includes user authentication with signup/login functionality and conversation management through a sidebar interface.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Framework
- **Framework**: Flask (Python web framework)
- **Rationale**: Lightweight and simple for building a chatbot interface with minimal setup
- **Session Management**: Flask sessions with a secret key for user authentication state

### AI Integration
- **Service**: Groq API for LLM completions
- **Client**: Official `groq` Python SDK
- **Configuration**: API key stored in environment variable `GROQ_API_KEY`
- **Personality**: Custom system prompt defines "Nova" as the chatbot with specific behavioral rules

### Authentication System
- **Password Storage**: SHA-256 hashing (via `hashlib`)
- **User Data**: Stored in Replit's key-value database with keys prefixed by `user:{username}`
- **Conversations**: Stored as JSON strings with keys prefixed by `convos:{username}`

### Data Storage
- **Database**: Replit DB (key-value store)
- **Fallback**: Graceful handling when Replit DB is unavailable (import wrapped in try/except)
- **Schema Pattern**:
  - `user:{username}` → hashed password
  - `convos:{username}` → JSON string of conversation history

### Frontend Architecture
- **Templating**: Jinja2 templates (Flask default)
- **Pages**: Login, Signup, and main Chat interface
- **Styling**: Inline CSS with dark theme (dark blue/black color scheme)
- **Layout**: Sidebar for conversation history + main chat area

### Route Structure
- `/` - Main chat interface (requires authentication)
- `/login` - User login page
- `/signup` - User registration page
- `/logout` - Session termination

## External Dependencies

### Python Packages
- `flask` - Web framework
- `groq` - Groq API client for LLM access

### External Services
- **Groq API** - Provides LLM capabilities for chat responses
- **Replit DB** - Key-value database for user accounts and conversation storage

### Environment Variables Required
- `GROQ_API_KEY` - API key for Groq service
- `FLASK_SECRET` - Secret key for Flask session management (falls back to "dev-secret")