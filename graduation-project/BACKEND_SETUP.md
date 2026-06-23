# Oil Spill Detection Dashboard

## Backend Setup Instructions

The backend for this application uses Docker, PostgreSQL, and Node.js/Express. Follow these steps to get started:

### Prerequisites
- Docker and Docker Compose installed
- (Optional) Node.js 18+ for local development

### Quick Start with Docker

1. **From the project root directory, start all services:**
   ```bash
   docker-compose up --build
   ```

   This will start:
   - PostgreSQL database on `localhost:5432`
   - Node.js backend server on `http://localhost:5000`

2. **The backend will automatically initialize the database on startup.**

3. **Test the backend is running:**
   ```bash
   curl http://localhost:5000/health
   ```

### Using the Application

1. **Start the frontend (in another terminal):**
   ```bash
   npm install
   npm run dev
   ```

2. **Access the application:**
   - Open `http://localhost:5173` in your browser
   - You'll be redirected to the login page

3. **Create an account or login:**
   - Click "Create one" to register a new account
   - Or use existing credentials if you've already registered

### Environment Configuration

Frontend environment variables are in `.env`:
```
VITE_API_URL=http://localhost:5000
```

Backend environment variables are in `backend/.env`:
```
PORT=5000
NODE_ENV=development
DB_HOST=postgres
DB_PORT=5432
DB_NAME=oil_spill_db
DB_USER=postgres
DB_PASSWORD=postgres
JWT_SECRET=your_super_secret_key_change_this_in_production
CORS_ORIGIN=http://localhost:5173
```

### Docker Compose Services

```bash
# View logs from all services
docker-compose logs -f

# View only backend logs
docker-compose logs -f backend

# View only database logs
docker-compose logs -f postgres

# Stop all services
docker-compose down

# Stop and remove all data
docker-compose down -v

# Restart services
docker-compose restart
```

### Database Management

Connect to the database:
```bash
docker-compose exec postgres psql -U postgres -d oil_spill_db
```

Useful SQL commands:
```sql
-- List all users
SELECT id, email, created_at FROM users;

-- Delete a user
DELETE FROM users WHERE email = 'user@example.com';

-- Reset database
DROP TABLE IF EXISTS users;
```

### Local Development (without Docker)

If you prefer to run without Docker:

1. **Install PostgreSQL** on your system

2. **From the `backend` directory:**
   ```bash
   npm install
   ```

3. **Configure `.env`:**
   ```
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=oil_spill_db
   DB_USER=postgres
   DB_PASSWORD=your_password
   ```

4. **Initialize database:**
   ```bash
   npm run db:init
   ```

5. **Start backend:**
   ```bash
   npm run dev
   ```

### Testing the API

**Register/Login:**
```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

**Verify Token:**
```bash
curl -X GET http://localhost:5000/api/auth/verify \
  -H "Authorization: Bearer <your_jwt_token>"
```

### Troubleshooting

**Port 5000 already in use:**
```bash
# Kill the process using port 5000
lsof -ti :5000 | xargs kill -9
```

**Database connection error:**
- Ensure `docker-compose` is running
- Check environment variables in `.env`
- Verify the database container is healthy: `docker-compose ps`

**Frontend can't connect to backend:**
- Check `.env` has correct `VITE_API_URL`
- Ensure backend is running: `curl http://localhost:5000/health`
- Check browser console for CORS errors

See [backend/README.md](./backend/README.md) for more detailed backend documentation.
