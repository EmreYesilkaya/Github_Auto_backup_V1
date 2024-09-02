# Github_Auto_backup_V1
[README.md](https://github.com/user-attachments/files/16835335/README.md)
# GitHub Backup Kubernetes Project
![github_backup_logo](https://github.com/user-attachments/assets/17a73013-76cb-456b-815f-7721d2159ea2)

## Overview

This project is designed as a learning exercise for understanding Kubernetes basics. It provides a simple solution for backing up GitHub repositories using Kubernetes. The project is not intended to be used in a professional production environment, but rather as a stepping stone for those who are new to Kubernetes and want to get hands-on experience.

## Features

- **Automated GitHub Backup**: The project includes a Python script that automatically backs up GitHub repositories.
- **Kubernetes Deployment**: The backup process is containerized and managed using Kubernetes.
- **Persistent Storage**: The backup data is stored on the local disk of the Kubernetes node using Persistent Volumes (PV) and Persistent Volume Claims (PVC).
- **Secrets Management**: GitHub tokens are securely stored using Kubernetes Secrets.

## Prerequisites

Before deploying this project, make sure you have the following:

- **Kubernetes Cluster**: A running Kubernetes cluster (e.g., Minikube, Docker Desktop with Kubernetes, or a managed Kubernetes service).
- **kubectl**: The Kubernetes command-line tool installed on your machine.
- **Docker**: Docker installed on your local machine.
- **GitHub Personal Access Token**: A GitHub token with repository access for backups.

## Installation

Follow these steps to set up and deploy the project:

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/yourusername/github-backup-kubernetes.git
    cd github-backup-kubernetes
    ```

2. **Build the Docker Image**:
    Build the Docker image using the provided `Dockerfile`.
    ```bash
    docker build -t yourusername/github-backup:latest .
    ```

3. **Push the Docker Image**:
    Push the Docker image to your container registry (e.g., Docker Hub).
    ```bash
    docker push yourusername/github-backup:latest
    ```

4. **Create the Kubernetes Namespace**:
    Apply the `Namespace.yaml` file to create a dedicated namespace.
    ```bash
    kubectl apply -f Namespace.yaml
    ```

5. **Set Up Persistent Volume and Persistent Volume Claim**:
    Apply the `pv.yaml` and `pvc.yaml` files to set up storage for the backups.
    ```bash
    kubectl apply -f pv.yaml
    kubectl apply -f pvc.yaml
    ```

6. **Create Secrets**:
    Replace `FILL THIS IN` in `secret.yaml` with your GitHub token (base64 encoded), then apply it to the cluster.
    ```bash
    kubectl apply -f updated_secret.yaml
    ```

7. **Deploy the Application**:
    Apply the deployment and service configurations.
    ```bash
    kubectl apply -f updated_backup_deployment.yaml
    kubectl apply -f service.yaml
    ```

8. **Port Forwarding**:
    Forward the service port to your local machine to access it.
    ```bash
    kubectl port-forward service/backup-service 8081:80 -n github
    ```

## How It Works

- The Python script (`github_backup.py`) runs inside a Docker container and automates the process of cloning GitHub repositories and saving them to local storage defined by the Persistent Volume.
- The Kubernetes Deployment manages the lifecycle of the container, ensuring it runs continuously or as scheduled.
- The Service object exposes the application, allowing access to the backup system via port forwarding.

## Scheduling Backups Every 12 Hours

To automatically schedule the backup process every 12 hours, a Kubernetes CronJob can be used. Here’s a sample configuration:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: github-backup-cronjob
  namespace: github
spec:
  schedule: "0 */12 * * *"  # Runs every 12 hours
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: github-backup
            image: yourusername/github-backup:latest
            env:
            - name: GITHUB_TOKEN
              valueFrom:
                secretKeyRef:
                  name: github-secret
                  key: token
            volumeMounts:
            - name: backup-storage
              mountPath: /app/github_backups
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: github-backup-pvc
          restartPolicy: OnFailure
```

This CronJob ensures that the backup is performed automatically every 12 hours.

## Accessing the Application

After setting up port forwarding, you can access the backup service using:

```bash
http://localhost:8081
```

## Troubleshooting

- **Pod Logs**: If something goes wrong, you can check the logs of the running pod.
    ```bash
    kubectl logs <pod-name> -n github
    ```
- **Persistent Volume Issues**: Ensure that the PV and PVC are correctly bound and functioning.

## Contributing

This project is a learning tool and contributions are welcome. If you have suggestions or improvements, please feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License.

---

**Note**: This project is intended for educational purposes and is not suitable for production environments.

## GitHub Backup Interface

This project includes a simple web interface to view and manage your GitHub backups. The interface allows you to:

- **View Backed-Up Repositories**: See a list of repositories that have been backed up and explore their contents.
- **View Logs**: Check the logs for backup activities, ensuring that everything is working as expected.

### Screenshots

1. **Backup Files List**
  ![Görüntü 2 09 2024 12 14](https://github.com/user-attachments/assets/115f45cf-b733-4550-822e-6d2f77f21b93)


2. **Main Panel**
  ![Görüntü 2 09 2024 12 14](https://github.com/user-attachments/assets/b3e65be0-79cc-44d4-b1c5-46674a22cb4b)


