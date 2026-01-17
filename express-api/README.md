# Express API Server for Agentic AI

A simple Express.js API server that provides user, task, and service management endpoints. This server is designed to work with the agentic AI system where the AI agent intelligently calls these APIs based on user queries.

## 📋 Overview

The Express API provides RESTful endpoints for:
- **User Management**: List, retrieve, and create users
- **Task Management**: List, create, update, and manage tasks
- **Service Management**: Monitor and control service status

## 🚀 Quick Start

### Installation

```bash
cd express-api
npm install
```

### Running the Server

```bash
# Development mode (with auto-reload)
npm run dev

# Production build
npm run build
npm start
```

The server will start on `http://localhost:3001`

### API Documentation

Visit `http://localhost:3001` to see a complete list of endpoints.

## 📚 API Endpoints

### Users

#### List All Users
```http
GET /api/users
```

Response:
```json
{
  "success": true,
  "count": 3,
  "data": [
    {
      "id": "user1",
      "name": "Alice Johnson",
      "email": "alice@example.com",
      "role": "admin",
      "created_at": "2024-01-17T10:00:00Z"
    }
  ]
}
```

#### Get User by ID
```http
GET /api/users/:id
```

Example:
```http
GET /api/users/user1
```

#### Create New User
```http
POST /api/users
Content-Type: application/json

{
  "name": "David Lee",
  "email": "david@example.com",
  "role": "developer"
}
```

### Tasks

#### List Tasks (with optional filters)
```http
GET /api/tasks?status=pending&assigned_to=user1
```

Query Parameters:
- `status`: Filter by status (pending, in_progress, completed)
- `assigned_to`: Filter by assigned user ID

Response:
```json
{
  "success": true,
  "count": 2,
  "filters": {
    "status": "pending",
    "assigned_to": "user1"
  },
  "data": [
    {
      "id": "task1",
      "title": "Fix login bug",
      "description": "Users cannot login with special characters",
      "status": "in_progress",
      "assigned_to": "user1",
      "created_at": "2024-01-17T10:00:00Z",
      "updated_at": "2024-01-17T10:00:00Z"
    }
  ]
}
```

#### Get Task by ID
```http
GET /api/tasks/:id
```

Example:
```http
GET /api/tasks/task1
```

#### Create New Task
```http
POST /api/tasks
Content-Type: application/json

{
  "title": "Update documentation",
  "description": "Update API docs for v2",
  "assigned_to": "user2",
  "status": "pending"
}
```

#### Update Task
```http
PUT /api/tasks/:id
Content-Type: application/json

{
  "status": "completed",
  "assigned_to": "user3"
}
```

### Services

#### List All Services
```http
GET /api/services
```

Response:
```json
{
  "success": true,
  "count": 3,
  "data": [
    {
      "id": "api-server",
      "name": "API Server",
      "status": "running",
      "last_check": "2024-01-17T10:00:00Z"
    }
  ]
}
```

#### Get Service Status
```http
GET /api/services/:id
```

Example:
```http
GET /api/services/api-server
```

#### Restart Service
```http
POST /api/services/:id/restart
```

Example:
```http
POST /api/services/database/restart
```

#### Stop Service
```http
POST /api/services/:id/stop
```

Example:
```http
POST /api/services/cache/stop
```

### Health Check
```http
GET /api/health
```

## 🔧 Integration with Agentic AI

The agentic AI system (`backend/app/agentic/api_agent.py`) automatically calls these endpoints based on user queries.

### Example Agentic Queries

When you type these in agentic mode, the system will automatically call the appropriate APIs:

1. **"List all users"** → Calls `GET /api/users`
2. **"Show pending tasks"** → Calls `GET /api/tasks?status=pending`
3. **"Who is assigned to task1?"** → Calls `GET /api/tasks/task1`
4. **"Create a task called 'Review PR' for user1"** → Calls `POST /api/tasks`
5. **"Mark task2 as completed"** → Calls `PUT /api/tasks/task2`
6. **"What is the database status?"** → Calls `GET /api/services/database`
7. **"Restart the API server"** → Calls `POST /api/services/api-server/restart`

## 📁 Project Structure

```
express-api/
├── src/
│   ├── server.ts          # Main Express app
│   ├── routes.ts          # API route definitions
│   ├── db.ts              # In-memory database
│   └── types.ts           # TypeScript type definitions
├── package.json
├── tsconfig.json
└── README.md
```

## 🗄️ Data Models

### User
```typescript
interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  created_at: string;
}
```

### Task
```typescript
interface Task {
  id: string;
  title: string;
  description: string;
  status: "pending" | "in_progress" | "completed";
  assigned_to: string;
  created_at: string;
  updated_at: string;
}
```

### Service
```typescript
interface Service {
  id: string;
  name: string;
  status: "running" | "stopped" | "error";
  last_check: string;
}
```

## ⚙️ Configuration

### Environment Variables

```bash
PORT=3001          # Server port (default: 3001)
NODE_ENV=development # Environment (development/production)
```

## 🧪 Testing APIs

### Using cURL

```bash
# Get all users
curl http://localhost:3001/api/users

# Create a user
curl -X POST http://localhost:3001/api/users \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"test@example.com","role":"developer"}'

# Get tasks by status
curl "http://localhost:3001/api/tasks?status=pending"

# Restart a service
curl -X POST http://localhost:3001/api/services/api-server/restart
```

### Using Postman

1. Import the API endpoints into Postman
2. Test each endpoint individually
3. Verify responses match the documentation

## 🚀 Deployment

### Docker

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3001
CMD ["npm", "start"]
```

### Production Checklist

- [ ] Use a real database (MongoDB, PostgreSQL, etc.)
- [ ] Add authentication and authorization
- [ ] Implement rate limiting
- [ ] Add request validation
- [ ] Enable HTTPS
- [ ] Set up logging and monitoring
- [ ] Implement proper error handling
- [ ] Add API documentation (Swagger/OpenAPI)

## 🔒 Security

Currently, this is a demo server without authentication. For production:

1. **Add Authentication**: JWT tokens, OAuth2, etc.
2. **Add Authorization**: Role-based access control (RBAC)
3. **Input Validation**: Validate all inputs
4. **Rate Limiting**: Prevent abuse
5. **CORS**: Configure appropriate CORS policies
6. **HTTPS**: Use TLS/SSL

## 📝 License

MIT

## 🤝 Contributing

This is a demo project for the agentic AI system. Feel free to extend it with:
- Additional endpoints
- Real database integration
- Authentication and authorization
- Advanced error handling
- Comprehensive logging

## 📧 Support

For issues or questions about the agentic integration, refer to the main documentation:
- `README_AGENTIC_SYSTEM.md`
- `API_AGENT_GUIDE.md`
