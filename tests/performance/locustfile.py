"""
Performance testing configuration using Locust.

Usage: locust -f locustfile.py --host=http://localhost:8000
"""
from locust import HttpUser, task, between


class StatementXLUser(HttpUser):
    """Simulated user for load testing."""
    
    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks
    
    def on_start(self):
        """Called when user starts - register and login."""
        # Register a test user
        email = f"test_{self.environment.runner.user_count}@example.com"
        self.client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Load Test User",
        })
        
        # Login
        response = self.client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "TestPass123!",
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            self.client.headers["Authorization"] = f"Bearer {token}"
    
    @task(10)
    def health_check(self):
        """Check health endpoint (most common)."""
        self.client.get("/health")
    
    @task(5)
    def get_templates(self):
        """Fetch template library."""
        self.client.get("/api/v1/library/templates")
    
    @task(3)
    def get_me(self):
        """Get current user profile."""
        self.client.get("/api/v1/auth/me")
    
    @task(2)
    def get_documents(self):
        """List user documents."""
        self.client.get("/api/v1/documents")
    
    @task(1)
    def upload_document(self):
        """Upload a sample PDF (simulated)."""
        # Create a minimal PDF for testing
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        files = {"file": ("test.pdf", pdf_content, "application/pdf")}
        self.client.post("/api/v1/upload", files=files)


class AdminUser(HttpUser):
    """Admin user for load testing admin endpoints."""
    
    wait_time = between(5, 10)
    weight = 1  # Less common than regular users
    
    @task
    def get_metrics(self):
        """Check metrics endpoint."""
        self.client.get("/metrics")
    
    @task
    def get_audit_log(self):
        """Check audit log."""
        self.client.get("/api/v1/audit")
