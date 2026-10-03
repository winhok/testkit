from locust import HttpUser, task, constant
class CatalogUser(HttpUser):
    wait_time = constant(1)
    @task
    def catalog(self):
        with self.client.get('/catalog', name='catalog', catch_response=True) as response:
            if response.status_code != 200:
                response.failure('catalog status differs from 200')
