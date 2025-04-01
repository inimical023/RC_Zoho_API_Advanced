# RingCentral-Zoho CRM Integration

A modern web application to integrate RingCentral call data with Zoho CRM leads. This application processes both missed and accepted calls, attaches call recordings to leads, and provides a user-friendly dashboard for monitoring and management.

## Architecture

This application uses a hybrid architecture with:

- **Backend**: FastAPI (Python) RESTful API with SQLAlchemy ORM
- **Frontend**: React with Material UI and TypeScript
- **Task Processing**: Celery with Redis for background tasks and scheduling
- **Database**: PostgreSQL for persistent storage
- **Container Orchestration**: Docker Compose for easy deployment

## Features

- Process both missed and accepted calls from RingCentral
- Create or update leads in Zoho CRM
- Attach call recordings to leads
- Round-robin assignment of leads to Zoho CRM users
- Secure credential storage with encryption
- Role-based access control
- Background task processing
- Automatic scheduled tasks
- Modern web-based dashboard with statistics and management
- RESTful API for extensibility

## Prerequisites

### Required Software
- **Docker Desktop** (version 20.10.0 or higher)
  - [Download for Windows](https://docs.docker.com/desktop/install/windows-install/)
  - [Download for macOS](https://docs.docker.com/desktop/install/mac-install/)
  - [Download for Linux](https://docs.docker.com/desktop/install/linux-install/)
- **Docker Compose** (version 2.0.0 or higher, included with Docker Desktop)
- **Git** for cloning the repository
  - [Download Git](https://git-scm.com/downloads)

### API Credentials

#### RingCentral API
1. Create a RingCentral developer account at [https://developers.ringcentral.com/](https://developers.ringcentral.com/)
2. Create a new application in the RingCentral Developer Console
3. Select 'Server-Only (No UI)' application type
4. Enable the following permissions:
   - Read Call Log
   - Read Call Recording
   - Read Accounts
   - Read Extensions
5. Note your Client ID and Client Secret
6. Generate a JWT token with the appropriate scopes
7. Obtain your RingCentral Account ID from your account settings

#### Zoho CRM API
1. Register for a Zoho Developer account at [https://api-console.zoho.com/](https://api-console.zoho.com/)
2. Create a new Self-Client application
3. Enable the following scopes:
   - ZohoCRM.modules.ALL
   - ZohoCRM.settings.ALL
   - ZohoCRM.users.ALL
4. Generate a refresh token using the OAuth2 flow:
   - Detailed instructions: [Zoho API Documentation](https://www.zoho.com/crm/developer/docs/api/auth-request.html)
5. Note your Client ID, Client Secret, and Refresh Token

## Setup

### Production Deployment

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd new_project
   ```

2. Create a `.env` file in the project root with the following content:
   ```
   # Security (generate strong random strings for these values)
   SECRET_KEY=your_secret_key_for_jwt_tokens
   ENCRYPTION_KEY=your_encryption_key_for_credentials
   
   # Admin user (for initial setup)
   ADMIN_USERNAME=admin
   ADMIN_EMAIL=admin@example.com
   ADMIN_PASSWORD=secure_password
   
   # Database configuration
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_database_password
   POSTGRES_DB=rc_zoho_integration
   
   # Redis configuration
   REDIS_PASSWORD=your_redis_password
   
   # Application ports (change if needed)
   BACKEND_PORT=8000
   FRONTEND_PORT=3000
   
   # Environment (production or development)
   NODE_ENV=production
   ```

3. Configure resource limits in `docker-compose.yml` (optional):
   - Edit the file to adjust CPU and memory limits for each service
   - Default settings should work for most moderate workloads

4. Start the application using Docker Compose:
   ```bash
   # Pull the latest images
   docker-compose pull
   
   # Start all services in detached mode
   docker-compose up -d
   ```

5. Monitor the startup process:
   ```bash
   docker-compose logs -f
   ```

6. Verify all services are running:
   ```bash
   docker-compose ps
   ```
   All services should show status as "Up"

7. Access the application at `http://localhost:3000` (or the custom port if you changed it)

8. Log in with the default admin credentials you set in the `.env` file

9. Configure API credentials in the Settings page:
   - **RingCentral Configuration**:
     - Client ID: Your RingCentral application Client ID
     - Client Secret: Your RingCentral application Client Secret
     - JWT Token: Your generated JWT token
     - Account ID: Your RingCentral Account ID
   - **Zoho CRM Configuration**:
     - Client ID: Your Zoho Client ID
     - Client Secret: Your Zoho Client Secret
     - Refresh Token: Your Zoho Refresh Token
     - Data Center: Select the appropriate Zoho data center (US, EU, IN, etc.)

10. Configure lead assignment and call processing rules in the Settings page:
    - Set lead assignment mode (round-robin or fixed assignment)
    - Configure user mappings between RingCentral extensions and Zoho users
    - Set call processing rules (how to handle missed vs. accepted calls)
    - Set synchronization frequency

### Updating the Application

To update the application to the latest version:

```bash
# Pull the repository changes
git pull

# Pull the latest Docker images
docker-compose pull

# Restart the services
docker-compose down
docker-compose up -d
```

## Development Setup

For developers who want to modify or extend the application:

### Backend Development

1. Ensure you have Python 3.9+ installed:
   ```bash
   python --version
   ```

2. Create and activate a virtual environment:
   ```bash
   # On Linux/macOS
   cd backend
   python -m venv venv
   source venv/bin/activate
   
   # On Windows (Command Prompt)
   cd backend
   python -m venv venv
   venv\Scripts\activate.bat
   
   # On Windows (PowerShell)
   cd backend
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the backend directory:
   ```
   # Environment
   DEBUG=True
   
   # Database
   DATABASE_URL=postgresql://postgres:your_password@localhost:5432/rc_zoho_integration
   
   # Security
   SECRET_KEY=your_dev_secret_key
   ENCRYPTION_KEY=your_dev_encryption_key
   
   # Redis
   REDIS_URL=redis://:your_redis_password@localhost:6379/0
   
   # Cors
   ALLOWED_ORIGINS=http://localhost:3000
   
   # Default Admin
   ADMIN_USERNAME=admin
   ADMIN_EMAIL=admin@example.com
   ADMIN_PASSWORD=dev_password
   ```

5. Start the local PostgreSQL and Redis services using Docker:
   ```bash
   docker-compose up -d db redis
   ```

6. Initialize the database:
   ```bash
   python init_db.py
   ```

7. Run the application with hot-reloading:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

8. The backend API will be available at `http://localhost:8000`

### Frontend Development

1. Ensure you have Node.js (version 16+) and npm installed:
   ```bash
   node --version
   npm --version
   ```

2. Navigate to the frontend directory and install dependencies:
   ```bash
   cd frontend
   npm install
   ```

3. Create a `.env` file in the frontend directory:
   ```
   REACT_APP_API_URL=http://localhost:8000
   REACT_APP_VERSION=$npm_package_version
   REACT_APP_ENV=development
   ```

4. Start the development server:
   ```bash
   npm start
   ```

5. The frontend application will be available at `http://localhost:3000`

6. For production builds:
   ```bash
   npm run build
   ```

## Testing

### Backend Tests

```bash
cd backend
pytest
```

### Frontend Tests

```bash
cd frontend
npm test
```

## Configuration Options

### Environment Variables

All environment variables are documented in the `.env.example` files in both the root directory and the backend/frontend directories.

### Application Settings

Additional configuration is available through the web interface:

1. **General Settings**:
   - Application name and branding
   - Logging level
   - Task frequency (calls polling, sync operations)

2. **User Management**:
   - Create, edit, and delete users
   - Assign user roles (Admin, Manager, User)
   - Reset user passwords

3. **Integration Settings**:
   - API credential management
   - Lead field mapping customization
   - Call recording attachment settings
   - Call disposition rules

## Troubleshooting

### Common Issues

1. **Docker containers fail to start**:
   - Check Docker logs: `docker-compose logs`
   - Ensure ports are not already in use
   - Verify environment variables in the `.env` file

2. **Database connection issues**:
   - Check PostgreSQL logs: `docker-compose logs db`
   - Verify database credentials in environment variables
   - Check network connectivity between containers

3. **API credentials not working**:
   - Verify the credentials in the Settings page
   - Check token expiration dates
   - Review API permission scopes

4. **Missing call recordings**:
   - Verify RingCentral permissions include call recording access
   - Check storage paths in the application settings
   - Review RingCentral recording retention policies

### Logs

Application logs are available through Docker:

```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs backend
docker-compose logs frontend
docker-compose logs celery

# Follow logs in real-time
docker-compose logs -f
```

### Support and Resources

- GitHub Issues: [Report bugs or request features](https://github.com/your-repository/issues)
- Documentation: See the `docs/` directory for additional documentation
- API Documentation: Available at `http://localhost:8000/docs` when the application is running

## Backup and Restore

### Database Backup

```bash
docker-compose exec db pg_dump -U postgres rc_zoho_integration > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Database Restore

```bash
cat backup_file.sql | docker-compose exec -T db psql -U postgres rc_zoho_integration
```

## Security Recommendations

- Always use strong, unique passwords for all services
- Rotate API keys and secrets regularly
- Enable HTTPS in production environments
- Use a reverse proxy (such as Nginx) in front of the application
- Implement regular backups of the database
- Keep all software updated to the latest versions
- Use network segmentation to isolate the application
- Implement IP whitelisting for administrative access

## Performance Tuning

For high-volume environments:

1. Increase resources in `docker-compose.yml`:
   ```yaml
   services:
     backend:
       deploy:
         resources:
           limits:
             cpus: '2'
             memory: 2G
   ```

2. Enable database connection pooling
3. Adjust Celery worker count based on server capacity
4. Implement caching for frequently accessed data

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

This project is based on a migration from a batch processing approach to a modern web application architecture. 