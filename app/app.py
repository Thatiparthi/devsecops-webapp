from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return "Hello from DevSecOps Kubernetes Application!"


@app.route("/health")
def health():
    return "UP"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)