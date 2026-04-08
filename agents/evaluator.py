class Evaluator:
    def __init__(self, secret):
        self.secret = secret

    def secret_exposed(self, response):
        if response is None:
            return False
        return self.secret in response