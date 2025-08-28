# Dynamic Badges Setup Instructions

If you want dynamic badges that update automatically, follow these steps:

## Option 1: Use Current Static Badges (Recommended)
The README.md already contains static badges that show:
- ![Tests](https://github.com/Migelo/telegram-whisper-bot/workflows/Tests/badge.svg) - Auto-updates based on CI status
- ![Python](https://img.shields.io/badge/python-3.12-blue) - Shows Python version
- ![Tests Count](https://img.shields.io/badge/tests-106-brightgreen) - Shows test count
- ![License](https://img.shields.io/badge/license-MIT-green) - Shows license

## Option 2: Set Up Dynamic Badges with Gist

### Step 1: Create a Gist
1. Go to https://gist.github.com/
2. Create a new **public** gist
3. Add any file (e.g., `badges.json`) with some content
4. Save the gist and copy the gist ID from the URL

### Step 2: Update badges.yml
Edit `.github/workflows/badges.yml` and replace `YOUR_GIST_ID_HERE` with your actual gist ID.

### Step 3: Add Dynamic Coverage Badge (Optional)
To get real coverage percentage:

```yaml
- name: Extract coverage percentage
  run: |
    COVERAGE=$(python -m pytest tests/ --cov=. --cov-report=term-missing | grep "TOTAL" | awk '{print $4}' | sed 's/%//')
    echo "COVERAGE_PERCENT=${COVERAGE}%" >> $GITHUB_ENV

- name: Create coverage badge
  uses: schneegans/dynamic-badges-action@v1.7.0
  with:
    auth: ${{ secrets.GITHUB_TOKEN }}
    gistID: YOUR_GIST_ID_HERE
    filename: coverage.json
    label: Coverage
    message: ${{ env.COVERAGE_PERCENT }}
    color: green
```

### Step 4: Use Badge URLs in README
Replace static badges with gist badge URLs:
```markdown
![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/USERNAME/GIST_ID/raw/coverage.json)
![Tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/USERNAME/GIST_ID/raw/tests.json)
```

## Option 3: Alternative Badge Services

### Codecov Badge
If you set up Codecov (already configured in the workflow):
```markdown
![Coverage](https://codecov.io/gh/Migelo/telegram-whisper-bot/branch/main/graph/badge.svg)
```

### GitHub Actions Badge (Already Working)
```markdown
![Tests](https://github.com/Migelo/telegram-whisper-bot/workflows/Tests/badge.svg)
```

## Recommendation
The current static badges in README.md are sufficient for most projects and don't require additional setup. They show:
- CI status (auto-updating)
- Python version
- Test count
- License

Only set up dynamic badges if you need auto-updating coverage percentages or other metrics.