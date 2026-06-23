# Oil Spill Detection Backend

Backend API for the Oil Spill Detection Dashboard with PostgreSQL authentication.

## Prerequisites

- Docker and Docker Compose installed
- Node.js 18+ (for local development without Docker)
- npm or yarn

## Quick Start with Docker

### 1. Copy environment file

```bash
cp .env.example .env
```

### 2. Start services

From the root directory of the project:

```bash
docker-compose up --build
```

This will start:
- PostgreSQL database on `localhost:5432`
- Node.js backend server on `http://localhost:5000`

### 3. Initialize the database

The database will automatically create the users table when the backend starts.

## API Endpoints

### Authentication

#### Register
- **POST** `/api/auth/register`
- **Body**: 
  ```json
  {
    "email": "user@example.com",
    "password": "password123"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "message": "User registered successfully",
    "token": "jwt_token_here",
    "user": {
      "id": "uuid",
      "email": "user@example.com"
    }
  }
  ```

#### Login
- **POST** `/api/auth/login`
- **Body**: 
  ```json
  {
    "email": "user@example.com",
    "password": "password123"
  }
  ```
- **Response**: Same as register

#### Verify Token
- **GET** `/api/auth/verify`
- **Headers**: `Authorization: Bearer <jwt_token>`
- **Response**:
  ```json
  {
    "success": true,
    "message": "Token is valid",
    "user": {
      "id": "uuid",
      "email": "user@example.com"
    }
  }
  ```

## Local Development (without Docker)

### 1. Install dependencies

```bash
cd backend
npm install
```

### 2. Set up PostgreSQL

Make sure PostgreSQL is running on your machine.

### 3. Configure environment

```bash
cp .env.example .env
# Update .env with your database credentials
```

### 4. Initialize database

```bash
npm run db:init
```

### 5. Start development server

```bash
npm run dev
```

## Project Structure

```
backend/
├── src/
│   ├── index.ts              # Main server file
│   ├── controllers/          # Route handlers
│   │   └── authController.ts # Authentication logic
│   ├── routes/               # API routes
│   │   └── auth.ts           # Auth routes
│   ├── middleware/           # Express middleware
│   │   └── auth.ts           # JWT authentication middleware
│   ├── database/             # Database configuration
│   │   ├── pool.ts           # PostgreSQL connection pooling
│   │   └── init.ts           # Database initialization
│   └── types/                # TypeScript types
│       └── index.ts          # Shared types
├── package.json              # Dependencies
├── tsconfig.json             # TypeScript configuration
├── Dockerfile                # Docker configuration
└── .env                      # Environment variables
```

## Environment Variables

```
PORT=5000                                    # Backend port
NODE_ENV=development                         # Node environment
DB_HOST=postgres                             # Database host
DB_PORT=5432                                 # Database port
DB_NAME=oil_spill_db                         # Database name
DB_USER=postgres                             # Database user
DB_PASSWORD=postgres                         # Database password
JWT_SECRET=your_secret_key                   # JWT signing secret
JWT_EXPIRY=7d                                # JWT token expiry
CORS_ORIGIN=http://localhost:5173            # Frontend CORS origin
```

## Database Schema

### Users Table
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
```

## Development Commands

```bash
# Start development server (with auto-reload)
npm run dev

# Build TypeScript
npm run build

# Start production server
npm start

# Initialize database
npm run db:init
```

## Docker Commands

```bash
# Start all services
docker-compose up

# Stop all services
docker-compose down

# View logs
docker-compose logs -f backend
docker-compose logs -f postgres

# Connect to PostgreSQL in Docker
docker-compose exec postgres psql -U postgres -d oil_spill_db
```

## Security Notes

⚠️ **Important for Production**:
- Change `JWT_SECRET` to a strong random string
- Use HTTPS in production
- Use environment variables for sensitive data
- Implement rate limiting for login endpoints
- Add input validation and sanitization
- Use proper CORS configuration
- Enable SSL for PostgreSQL connections

## Testing

```bash
# Test login endpoint
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

# Test register endpoint
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

# Test verify endpoint
curl -X GET http://localhost:5000/api/auth/verify \
  -H "Authorization: Bearer <your_jwt_token>"

# Test health check
curl http://localhost:5000/health
```

## Troubleshooting

### Database connection failed
- Check if PostgreSQL is running
- Verify database credentials in `.env`
- Ensure `DB_HOST` matches your setup (use `postgres` for Docker, `localhost` for local)

### Port already in use
- Change `PORT` in `.env` to another value
- Or kill the process using the port: `lsof -ti :5000 | xargs kill -9`

### Module not found errors
- Run `npm install` to install dependencies
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`

## Next Steps

1. Connect frontend to this backend (update Login component)
2. Add user profile endpoints
3. Add password reset functionality
4. Implement refresh tokens
5. Add email verification
6. Add rate limiting

## License

MIT
