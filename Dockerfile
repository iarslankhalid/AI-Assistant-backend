FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application code
COPY . .

# Expose FastAPI port
EXPOSE 12000

# Run the app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "12000"]
