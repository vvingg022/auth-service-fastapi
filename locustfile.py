import random
from locust import HttpUser, task, between

EMAIL = "loadtest@example.com"
PASSWORD = "LoadTest#12345"


class ApiUser(HttpUser):
    wait_time = between(0.5, 1.5)  # a real user pauses between actions

    def on_start(self):
        # Register once (ignore "already exists"), then log in to get a token
        with self.client.post(
            "/api/auth/register",
            json={"name": "Load Test", "email": EMAIL, "password": PASSWORD},
            catch_response=True,
        ) as r:
            r.success()
            
        r = self.client.post(
            "/api/auth/login",  # CHECK path and body fields
            json={"email": EMAIL, "password": PASSWORD},
            name="login (bcrypt)",
        )
        token = r.json().get("access_token") if r.status_code == 200 else None
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    @task(5)
    def health(self):
        self.client.get("/health")

    @task(4)
    def me(self):
        self.client.get("/api/auth/me", headers=self.headers, name="/me (JWT)")  # CHECK path