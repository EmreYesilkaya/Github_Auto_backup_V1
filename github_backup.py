import os, requests, json, logging, time, hashlib, shutil, subprocess, zipfile, io
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, send_from_directory, render_template_string, abort, send_file, jsonify
from threading import Thread
from requests.exceptions import RequestException
from dotenv import load_dotenv
from collections import defaultdict, deque

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()
BACKUP_DIR = os.path.abspath("github_backups")
MAX_LOG_ENTRIES = 100
log_entries = deque(maxlen=MAX_LOG_ENTRIES)

class GithubBackup:
    def __init__(self, token):
        self.token = token
        self.headers = {'Authorization': f'token {token}'}
        self.backup_folder = BACKUP_DIR
        self.max_retries = 3
        self.retry_delay = 5
        self.max_versions = 5

    def get_github_repos(self):
        url = 'https://api.github.com/user/repos'
        repos = []
        while url:
            for attempt in range(self.max_retries):
                try:
                    response = requests.get(url, headers=self.headers)
                    response.raise_for_status()
                    repos.extend(response.json())
                    url = response.links.get('next', {}).get('url')
                    break
                except RequestException as e:
                    logger.error(f"Failed to fetch repositories: {e}")
                    time.sleep(self.retry_delay)
            else:
                logger.error(f"Failed to fetch repositories after {self.max_retries} attempts")
                break
        return repos

    def backup_repos(self, repos):
        os.makedirs(self.backup_folder, exist_ok=True)
        for repo in repos:
            self.backup_repo(repo)

    def backup_repo(self, repo):
        repo_folder = os.path.join(self.backup_folder, repo['name'])
        current_hash = self.calculate_hash(repo_folder) if os.path.exists(repo_folder) else None
        temp_folder = f"{repo_folder}_temp"
        os.makedirs(temp_folder, exist_ok=True)
        if self.download_repo_contents(repo['name'], repo['clone_url'], temp_folder):
            new_hash = self.calculate_hash(temp_folder)
            if current_hash != new_hash:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                backup_path = f"{repo_folder}_{timestamp}"
                shutil.move(temp_folder, backup_path)
                logger.info(f"Backed up {repo['name']} to {backup_path}")
                log_entries.append(f"Backed up {repo['name']} to {backup_path}")
                self.cleanup_old_versions(repo['name'])
            else:
                logger.info(f"No changes in {repo['name']}, skipping backup.")
                log_entries.append(f"No changes in {repo['name']}, skipping backup.")
                shutil.rmtree(temp_folder)
        else:
            logger.error(f"Failed to backup {repo['name']}")
            log_entries.append(f"Failed to backup {repo['name']}")

    def download_repo_contents(self, repo_name, clone_url, temp_folder):
        try:
            subprocess.run(['git', 'clone', '--depth', '1', clone_url, temp_folder], check=True, capture_output=True)
            logger.info(f"Successfully cloned {repo_name}")
            log_entries.append(f"Successfully cloned {repo_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone {repo_name}: {e}")
            log_entries.append(f"Failed to clone {repo_name}: {e}")
            return False

    def calculate_hash(self, folder):
        hash_object = hashlib.md5()
        for root, _, files in os.walk(folder):
            for file in files:
                file_path = os.path.join(root, file)
                with open(file_path, 'rb') as f:
                    hash_object.update(f.read())
        return hash_object.hexdigest()

    def cleanup_old_versions(self, repo_name):
        versions = sorted([d for d in os.listdir(self.backup_folder) if d.startswith(f"{repo_name}_")], reverse=True)
        for old_version in versions[self.max_versions:]:
            old_version_path = os.path.join(self.backup_folder, old_version)
            shutil.rmtree(old_version_path)
            logger.info(f"Removed old version: {old_version}")
            log_entries.append(f"Removed old version: {old_version}")

app = Flask(__name__)

@app.route('/')
def index():
    files = defaultdict(list)
    for root, _, filenames in os.walk(BACKUP_DIR):
        for filename in filenames:
            rel_dir = os.path.relpath(root, BACKUP_DIR)
            rel_file = os.path.join(rel_dir, filename)
            repo_name = rel_dir.split('_')[0]
            files[repo_name].append(rel_file)

    html = """
    <!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GitHub Backups</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .repo-card { margin-bottom: 10px; }
        .repo-header { 
            background-color: #f8f9fa; 
            padding: 10px 15px; 
            border: 1px solid #dee2e6;
            border-radius: 5px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .repo-body { 
            padding: 15px; 
            border: 1px solid #dee2e6;
            border-top: none;
            display: none;
        }
        .download-all-btn { margin-bottom: 10px; }
        #logPanel { 
            height: 300px; 
            overflow-y: auto; 
            background-color: #f8f9fa; 
            border: 1px solid #dee2e6; 
            padding: 10px; 
            font-family: monospace; 
        }
    </style>
</head>
<body>
    <div class="container mt-5">
        <h1 class="mb-4">GitHub Backups</h1>
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">Log Panel</div>
                    <div class="card-body">
                        <div id="logPanel"></div>
                    </div>
                </div>
            </div>
        </div>
        <div id="repoCards"></div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let isAutoScrollEnabled = true;

        function updateLogs() {
            fetch('/logs')
                .then(response => response.json())
                .then(data => {
                    const logPanel = document.getElementById('logPanel');
                    logPanel.innerHTML = data.logs.join('<br>');
                    if (isAutoScrollEnabled) {
                        logPanel.scrollTop = logPanel.scrollHeight;
                    }
                });
        }

        function updateRepoCards() {
            fetch('/repo_data')
                .then(response => response.json())
                .then(data => {
                    const repoCards = document.getElementById('repoCards');
                    repoCards.innerHTML = '';
                    for (const [repo, backups] of Object.entries(data)) {
                        const card = document.createElement('div');
                        card.className = 'repo-card';
                        card.innerHTML = `
                            <div class="repo-header" onclick="toggleRepoBody(this)">
                                <h5 class="mb-0">${repo}</h5>
                                <button class="btn btn-sm btn-outline-primary">Toggle</button>
                            </div>
                            <div class="repo-body">
                                <a href="/download_all/${repo}" class="btn btn-primary download-all-btn">Download All Versions</a>
                                <ul class="list-group">
                                    ${backups.map(backup => `
                                        <li class="list-group-item">
                                            <a href="/backups/${backup}">${backup.split('/').pop()}</a>
                                        </li>
                                    `).join('')}
                                </ul>
                            </div>
                        `;
                        repoCards.appendChild(card);
                    }
                });
        }

        function toggleRepoBody(header) {
            const body = header.nextElementSibling;
            body.style.display = body.style.display === 'none' ? 'block' : 'none';
        }

        document.getElementById('logPanel').addEventListener('scroll', function() {
            isAutoScrollEnabled = (this.scrollTop + this.clientHeight === this.scrollHeight);
        });

        setInterval(updateLogs, 5000);
        setInterval(updateRepoCards, 30000);
        updateLogs();
        updateRepoCards();
    </script>
</body>
</html>
    """
    return render_template_string(html)

@app.route('/logs')
def get_logs():
    return jsonify({'logs': list(log_entries)})

@app.route('/repo_data')
def get_repo_data():
    files = defaultdict(list)
    for root, _, filenames in os.walk(BACKUP_DIR):
        for filename in filenames:
            rel_dir = os.path.relpath(root, BACKUP_DIR)
            rel_file = os.path.join(rel_dir, filename)
            repo_name = rel_dir.split('_')[0]
            files[repo_name].append(rel_file)
    return jsonify(files)

@app.route('/backups/<path:filename>')
def download_file(filename):
    try:
        return send_from_directory(BACKUP_DIR, filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)

@app.route('/download_all/<repo_name>')
def download_all(repo_name):
    repo_backups = [d for d in os.listdir(BACKUP_DIR) if d.startswith(f"{repo_name}_")]
    if not repo_backups:
        abort(404)

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for backup in repo_backups:
            backup_path = os.path.join(BACKUP_DIR, backup)
            for root, _, files in os.walk(backup_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, BACKUP_DIR)
                    zf.write(file_path, arcname)

    memory_file.seek(0)
    return send_file(memory_file, mimetype='application/zip', as_attachment=True, download_name=f'{repo_name}_all_backups.zip')

def main_backup():
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable is not set")
        return

    backup = GithubBackup(github_token)

    while True:
        try:
            repos = backup.get_github_repos()
            if repos:
                backup.backup_repos(repos)
                logger.info("Checked and backed up repositories. Sleeping for 10 minutes.")
                log_entries.append("Checked and backed up repositories. Sleeping for 10 minutes.")
            else:
                logger.warning("No repositories found or unable to fetch repositories.")
                log_entries.append("No repositories found or unable to fetch repositories.")
        except Exception as e:
            logger.exception(f"An unexpected error occurred: {e}")
            log_entries.append(f"An unexpected error occurred: {e}")
        time.sleep(600)  # 10 minutes

if __name__ == '__main__':
    backup_thread = Thread(target=main_backup)
    backup_thread.start()
    app.run(host='0.0.0.0', port=8081, debug=True)