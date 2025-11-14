# EasyTesting

A comprehensive testing platform built with Django, Django REST Framework, SQLite, Bootstrap, and HTTPRunner.

## Features

- Create and manage test projects
- Define test environments with variables
- Create API test cases with request details and validation rules
- Organize test cases into test suites
- Execute tests and view results
- RESTful API for integration with other tools

## Installation

1. Clone the repository
2. Create a virtual environment:
   \`\`\`
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   \`\`\`
3. Install dependencies:
   \`\`\`
   pip install -r requirements.txt
   \`\`\`
4. Run migrations:
   \`\`\`
   python manage.py migrate
   \`\`\`
5. Create a superuser:
   \`\`\`
   python manage.py createsuperuser
   \`\`\`
6. Run the development server:
   \`\`\`
   python manage.py runserver
   \`\`\`

## Usage

1. Access the admin interface at http://localhost:8000/admin/
2. Log in with your superuser credentials
3. Create projects, environments, test cases, and test suites
4. Execute tests and view results

## API Documentation

The platform provides a RESTful API for integration with other tools. The API endpoints are:

- `/api/projects/` - Manage projects
- `/api/environments/` - Manage environments
- `/api/test-cases/` - Manage test cases
- `/api/test-suites/` - Manage test suites
- `/api/test-runs/` - Manage test runs
- `/api/test-results/` - View test results

## License

MIT
