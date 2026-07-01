# Online Cinema

---

## Running with Docker

To launch the complete environment with one command:

```bash
docker-compose up --build
```

### Service Access Points

* **API Docs (Swagger):** [http://localhost:8000/docs](https://www.google.com/search?q=http://localhost:8000/docs)
* **MinIO Object Storage Console:** [http://localhost:9001](https://www.google.com/search?q=http://localhost:9001)

To stop the containers safely:

```bash
docker-compose down
```

## Git Workflow

Every task gets its own branch. Always branch from `develop`, always PR back to `develop`.

```bash
# Start a task
git checkout develop
git pull origin develop
git checkout -b feature/your-task-name

# Finish a task
git add .
git commit -m "feat: what you did"
git push -u origin feature/your-task-name
# open a Pull Request on GitHub → into develop
```

**Branch structure:**
```
master        ← never touch during the sprint
└── develop ← all PRs go here
    ├── feature/users-model
    ├── feature/doctors-slots
    └── feature/appointments-crud
```

**PR rules:** every PR needs 2 approvals before merging.

**If develop moved ahead of your branch:**
```bash
git checkout develop && git pull origin develop
git checkout feature/your-task-name
git rebase develop
git push --force-with-lease origin feature/your-task-name
```

---

## Commit Message Format

```
feat: add User model
fix: slot overlap validation
chore: update pyproject.toml
test: add tests for user
docs: update README
```
