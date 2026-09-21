# MINDS Medication Tracker

A lightweight digital medication tracking application for **MINDS**, a Singapore social-care organisation.

The application is intended to replace the physical medication administration log with a simple electronic medication administration record (eMAR) for a social-care/training environment.

> **Development status:** Prototype
> **Data:** Fake/test data only — do not use real trainee or medication information.

---

## Overview

The core workflow is:

```text
Medication due
      ↓
Training Officer sees medication
      ↓
Administer OR Cancel
      ↓
System records the outcome
      ↓
Historical record is retained
```

The application currently supports both **Training Officer** and **Manager** workflows.

---

## Current Technology

* **Frontend:** HTML, CSS, JavaScript
* **Backend:** Python + FastAPI
* **Database:** Azure SQL Database
* **Database driver:** Microsoft ODBC Driver 18 for SQL Server
* **Authentication:** Development login using staff records
* **Source control:** GitHub

Current development architecture:

```text
Browser
   ↓
HTML / JavaScript
   ↓
FastAPI
   ↓
Azure SQL Database
```

The prototype currently runs the FastAPI backend locally while connecting to Azure SQL.

---

## Project Structure

```text
medication-app/
│
├── frontend/
│   ├── index.html
│   ├── manager.html
│   └── history.html
│
├── backend/
│   ├── __init__.py
│   ├── database.py
│   └── main.py
│
├── .gitignore
├── README.md
└── .venv/
```

### Frontend

* `index.html` — Training Officer interface and login
* `manager.html` — Manager dashboard and management functions
* `history.html` — Historical medication records

### Backend

* `main.py` — FastAPI application and API endpoints
* `database.py` — Azure SQL connection

---

## Database

The current database contains four main tables.

### Trainees

Stores trainee information.

```text
trainee_id
name
unit
active
```

### Staff

Stores staff information.

```text
staff_id
name
role
unit
active
```

Roles currently include:

* Manager
* Training Officer

### Medications

Stores the recurring medication definition.

```text
medication_id
trainee_id
medication_name
dosage
frequency
scheduled_time
instructions
active
```

### MedicationLogs

Stores individual medication occurrences and their outcomes.

```text
log_id
medication_id
trainee_id
administration_date
scheduled_time
status
given_by
witnessed_by
actual_time
cancellation_reason
remarks
```

The database is the source of truth for medication administration records.

---

## Recurring Medication Scheduling

The prototype now supports automatic generation of medication occurrences.

A medication is defined once in the `Medications` table.

For example:

```text
M001 | T001 | Panadol | 1 tablet | Daily | 09:00
```

When today's medications are requested, the backend checks active medications and creates the corresponding `MedicationLogs` record if it does not already exist.

Example:

```text
Medication
    ↓
Daily schedule
    ↓
Today's MedicationLog
    ↓
Pending
```

### Current scheduling rules

* `Daily` currently means **Monday–Friday**
* Saturday and Sunday are excluded
* Public holiday handling is not implemented yet
* Specific-day scheduling is not implemented yet
* Unusual instructions can be recorded in the `instructions` field
* Multiple doses per day are represented by separate medication rows with different scheduled times
* Existing medication logs are not duplicated when the page is refreshed

Example:

```text
M001 | T001 | Panadol | 1 tablet | Daily | 09:00
M002 | T001 | Panadol | 1 tablet | Daily | 13:00
M003 | T001 | Panadol | 1 tablet | Daily | 18:00
```

These generate three separate medication occurrences.

---

## Medication Status

Medication logs use the following statuses:

```text
Pending
Administered
Cancelled
Not Administered
```

Expected workflow:

```text
Pending
   ├──→ Administered
   ├──→ Cancelled
   └──→ Not Administered
```

When a medication log is initially created:

```text
given_by = NULL
witnessed_by = NULL
actual_time = NULL
```

These fields are populated when the medication is administered.

Cancellation records retain the cancellation reason instead of deleting the medication log.

---

## Training Officer Functions

Training Officers can currently:

* Log in using development staff records
* View medications due today
* See trainee, medication, dosage and scheduled time
* See medication instructions
* Administer medication
* Record Given By
* Record Witnessed By
* Record actual administration time
* Add remarks
* Cancel medication
* Record cancellation reason
* View relevant history

The interface also handles loss of connection to the backend.

---

## Manager Functions

Managers can currently:

### Medication Overview

View today's medications and their status.

### Staff Management

* View staff
* Add staff
* Edit staff
* Activate/deactivate staff

### Trainee Management

* View trainees
* Add trainees
* Edit trainees
* Activate/deactivate trainees

### Medication Management

* View medications
* Add medications
* Edit medications
* Activate/deactivate medications
* Configure dosage
* Configure frequency
* Configure scheduled time
* Add instructions

The current medication frequency interface uses a dropdown with:

```text
Daily
```

This prevents unsupported free-text scheduling rules from being entered during the prototype.

---

## Development Setup

### Requirements

Install:

* Python 3
* Microsoft ODBC Driver 18 for SQL Server
* Git
* Azure CLI or Azure authentication tools if required for database authentication

The backend currently uses Azure Identity for authentication to Azure SQL.

---

## Running the Backend

From the project root:

```bash
source .venv/bin/activate
```

Then:

```bash
uvicorn backend.main:app --reload
```

The backend should start at:

```text
http://127.0.0.1:8000
```

The application includes a health endpoint:

```text
http://127.0.0.1:8000/health
```

---

## Running the Frontend

The frontend currently uses a local API URL:

```javascript
const API_URL = "http://127.0.0.1:8000";
```

Open the frontend through a local development server or the appropriate local hosting method.

Do not deploy the current development configuration directly to production.

---

## Environment Configuration

Database configuration is stored through environment variables rather than hard-coded credentials.

The `.env` file is intentionally excluded from GitHub.

Example variables include:

```text
DB_SERVER
DB_NAME
```

Never commit:

* Passwords
* Connection strings containing credentials
* Azure access tokens
* Storage keys
* `.env` files
* Real trainee information
* Real medication information

---

## Testing

The current prototype uses fake data such as:

```text
John Tan
Sarah Lim
David Lee
Emily Wong
Michael Goh
```

Basic tests should include:

1. A pending medication appears for today.
2. A Daily medication generates today's log.
3. Refreshing the page does not create a duplicate log.
4. Multiple scheduled times create separate occurrences.
5. Administration changes the status to `Administered`.
6. Actual administration time is recorded.
7. Given By and Witnessed By are recorded.
8. Cancellation records the reason.
9. Historical records remain available.
10. Inactive medications do not generate future occurrences.
11. Inactive trainees do not generate future occurrences.
12. Invalid medication/trainee IDs are rejected.

---

## Security

This is a medication-related application involving vulnerable persons.

**The current prototype must only use fake data.**

The current development login is not production-grade authentication.

The eventual production system should use:

* Microsoft Entra ID
* Role-based access control
* Unit-level authorisation
* HTTPS
* Backend-enforced permissions
* Secure Azure SQL access
* Managed identities/environment variables
* Azure Key Vault where appropriate
* Audit logging
* Database backups
* Restricted database/network access
* Private Blob Storage

UI restrictions alone are not security. Authorisation must be enforced by the backend.

---

## Planned Architecture

The eventual Azure architecture is:

```text
iPad / Laptop / Phone
          ↓
Azure App Service
          ↓
FastAPI Backend
       ↙     ↘
Azure SQL   Blob Storage
```

Authentication:

```text
Microsoft Entra ID
        ↓
Authenticated user
        ↓
FastAPI
        ↓
Role + Unit authorisation
```

The prototype should remain lightweight until the core workflow is stable.

---

## Planned Features

### Near term

* Validate recurring medication generation
* Validate the complete Training Officer workflow
* Improve historical record handling
* Fix remaining prototype issues

### Later

* Microsoft Entra ID authentication
* Proper role/unit authorisation
* Azure App Service deployment
* Azure Blob Storage for medication photos
* Excel/SharePoint historical record integration
* Audit logging
* Environment-specific configuration
* CI/CD
* Production security/networking
* Notifications and reporting

---

## Portability

The application is being developed under an **NTU Azure for Students** subscription but is intended to eventually be deployable in a **MINDS Azure/Microsoft environment**.

Application code should remain separate from:

* Azure subscription configuration
* Environment variables
* Credentials/secrets
* Production data
* Environment-specific URLs

The intended model is:

```text
Development
NTU Azure + fake data
        ↓
Same application code
        ↓
Production
MINDS Azure + MINDS-authorised data
```

---

## Cost Considerations

The prototype is being developed using Azure for Students credit.

Azure resources should be kept to the lowest-cost appropriate configuration.

Avoid unnecessary:

* Virtual machines
* Kubernetes
* Premium databases
* Always-on compute
* Complex networking
* Unnecessary Azure services

Any materially paid Azure resource should be evaluated for cost before deployment.

---

## Repository

GitHub repository:

**MINDS-Geylang-Serai/Medication-Tracker**

The repository should contain application code and reproducible database/development files, but never secrets or real client data.

---

## Development Principle

The goal is not simply to produce a student demonstration.

The goal is to build a **small, credible, secure and portable prototype** that could realistically be transferred to MINDS.

Build cleanly now, but defer enterprise-level complexity until it is actually required.
