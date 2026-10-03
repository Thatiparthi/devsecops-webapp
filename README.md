# DevSecOps Web App

A small Flask application used to demonstrate a secure CI/CD pipeline. GitHub Actions runs tests and SonarQube analysis, builds and scans a SHA-tagged container image, publishes it to GitHub Container Registry (GHCR), and deploys it to a temporary KIND cluster for runtime verification.

## Architecture

```text
Pull request or push to master
              |
              v
     Unit tests and syntax
              |
              v
 SonarQube analysis + Quality Gate
              |
              v
 Docker build + Trivy vulnerability scan
              |
       (push to master only)
              v
             GHCR
              |
              v
 KIND cluster on GitHub Actions runner
              |
   Namespace, Deployment, Service
              |
              v
      / and /health checks
```

## Application

The Flask app is in `app/` and listens on port `8080`.

| Endpoint | Response |
| --- | --- |
| `GET /` | `Hello from DevSecOps Kubernetes Application!` |
| `GET /health` | `UP` |

## Local development

Use Python 3.11:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r app/requirements.txt
python -m pip install pytest
pytest -q
python app/app.py
```

On Windows, activate the virtual environment with `.venv\Scripts\Activate.ps1`.

## Docker

Build and run the app locally:

```bash
docker build -t devsecops-webapp:local .
docker run --rm -p 8080:8080 devsecops-webapp:local
```

Visit `http://localhost:8080/` and `http://localhost:8080/health`.

## Minikube

The manifests retain the existing namespace, two-replica Deployment, probes, resource requests/limits, and port configuration. The Service is `ClusterIP`, which is suitable for the CI deployment and can be exposed locally with port-forwarding:

```bash
kubectl apply -f k8s/namespace.yml
kubectl apply -f k8s/deployment.yml
kubectl apply -f k8s/service.yml
kubectl rollout status deployment/devsecops -n devsecops
kubectl port-forward -n devsecops service/devsecops 8080:80
```

In another terminal, test `http://localhost:8080/` and `http://localhost:8080/health`. For local Minikube runs, build or load an image matching the image reference in `k8s/deployment.yml`; the GitHub workflow changes the image to its commit-specific GHCR reference during CI.

## GitHub Actions pipeline

The workflow is `.github/workflows/ci-cd.yml`. It triggers on pushes and pull requests targeting **`master`**.

1. `test` checks out the repository, configures Python 3.11, installs app/test dependencies, compiles the Python files, and runs pytest.
2. `sonarqube` runs after tests and waits for the SonarQube Quality Gate. A scan or gate failure blocks image build and deployment.
3. `docker-build-and-scan` builds the root Dockerfile with a tag based on the commit SHA. Trivy reports HIGH and CRITICAL findings; the reporting scan is non-blocking, while a second scan fails on CRITICAL findings. The scanned image is saved as a short-lived workflow artifact.
4. `publish-image` runs only on pushes to `master`, after tests, the Quality Gate, and Trivy pass. It loads the already-scanned image artifact and pushes it to GHCR.
5. `deploy` runs only on pushes to `master` after the image has been published. It creates KIND on the GitHub-hosted Ubuntu runner, applies the Kubernetes manifests, deploys the SHA-tagged image, waits for the rollout, and verifies both application endpoints through a port-forwarded ClusterIP Service.

The KIND cluster exists only for the deployment job. It is removed when the GitHub-hosted runner is discarded after the job.

### Trivy severity behavior

The first Trivy scan uses `severity: HIGH,CRITICAL` and `exit-code: "0"` so matching vulnerabilities are visible in the workflow log without failing solely because of HIGH findings. The second scan uses `severity: CRITICAL` and `exit-code: "1"`; a CRITICAL finding therefore fails the job and prevents GHCR publishing and deployment. Findings are not configured to be ignored.

## SonarQube configuration

Create a SonarQube project whose key matches `Thatiparthi_devsecops-webapp` in `sonar-project.properties`, then add these GitHub repository Actions secrets:

| Secret | Value |
| --- | --- |
| `SONAR_TOKEN` | A SonarQube analysis token for the project |
| `SONAR_HOST_URL` | The SonarQube server URL, for example `https://sonarqube.example.com` |

For SonarCloud, set `SONAR_HOST_URL` to `https://sonarcloud.io` and define a repository Actions variable named `SONAR_ORGANIZATION` with the SonarCloud organization key. Use a token with analysis permission for the project. Do not commit tokens or put credentials in `sonar-project.properties`.

## GHCR configuration

The workflow uses the automatically supplied `GITHUB_TOKEN` rather than a static registry token. The image name is derived from the repository owner/name (`ghcr.io/<owner>/<repository>`) and its only tag is `${{ github.sha }}`, making the deployed image immutable and traceable to a commit. The workflow does not deploy `latest`.

The build-and-scan job has `contents: read`; only the publish job receives `packages: write`. The deploy job has `contents: read` and `packages: read`. Ensure repository Actions settings allow these workflow permissions. For a private GHCR package, grant this repository Actions access to the package in the package's **Manage access** settings. The deploy job creates a short-lived Kubernetes `imagePullSecret` from `GITHUB_TOKEN` and attaches it to the namespace's default ServiceAccount, which the Deployment uses, so KIND can pull a private package without printing credentials or storing them in the manifests. A public package does not require registry credentials to pull, though this workflow still configures the secret.

## Kubernetes deployment

The workflow applies `k8s/namespace.yml`, `k8s/deployment.yml`, and `k8s/service.yml` to the KIND cluster. It then sets the Deployment image to the SHA-tagged image produced by the current workflow. The checked-in Deployment keeps its local image reference; it is not rewritten with a workflow-specific tag.

The Service is `ClusterIP` and exposes port `80` to container port `8080`. After `kubectl rollout status`, the workflow forwards the Service to the runner and checks the exact responses from `/` and `/health`. Any failed rollout or endpoint assertion fails the deployment job.

## Required GitHub configuration

- Repository secrets: `SONAR_TOKEN` and `SONAR_HOST_URL`.
- For SonarCloud only: repository Actions variable `SONAR_ORGANIZATION`.
- The workflow's built-in `GITHUB_TOKEN` needs package write access for publishing and package read access for deployment. No `KUBE_CONFIG_DATA` or Minikube access is needed; KIND is created inside the GitHub-hosted runner.
