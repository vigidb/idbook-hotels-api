# Base image with Python and pip
FROM python:3.12-alpine AS base

# Set the working directory
WORKDIR /app

# Install app dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt 
# Development stage
FROM base AS development

# Set the DJANGO_SETTINGS_MODULE for development
# ENV DJANGO_SETTINGS_MODULE=my_project.settings.development

# Expose the development port (optional: for running Django's development server)
EXPOSE 8000

# Apply migrations and start the development server
# CMD python manage.py IDBOOKAPI/makemigrations && python IDBOOKAPI/manage.py migrate && python manage.py IDBOOKAPI/runserver 0.0.0.0:8000
CMD python IDBOOKAPI/manage.py migrate && python manage.py IDBOOKAPI/runserver 0.0.0.0:8000

# Production stage
FROM base AS production

# Collect static files and prepare for production deployment (if needed)
# For example, if you use Django's "collectstatic" management command to collect static files,
# Apply migrations and start the production server
# If you are using Gunicorn as the production server, you can use the following line to start it:
# CMD ["gunicorn", "--bind", "0.0.0.0:8000", "qa.wsgi"]


