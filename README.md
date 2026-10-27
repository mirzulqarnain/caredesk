# CareDesk: clinic management system

Django web application with five modules: users and roles, appointment scheduling, medical records with lab
reports, billing, and dashboards with administration. Records are stored in **PostgreSQL on Amazon RDS**, uploaded
lab reports in **Amazon S3**. It deploys to **EC2** and to **Elastic Beanstalk** from the same code.

No third party services, no payment gateway, no JWT, no API keys. On AWS it reaches S3 through the server's IAM role.
The "online payment" is simulated inside the app.

## Run it on your computer (2 minutes)

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open http://127.0.0.1:8000. With no configuration it uses SQLite and a local `media/` folder, so you can try
everything before touching AWS.

Demo logins created by `seed_demo`:

| Role | Username | Password |
|---|---|---|
| Admin | `clinic_admin` | `admin123` |
| Front desk | `desk` | `desk123` |
| Doctor | `dr_amina`, `dr_bilal`, `dr_chen` | `doctor123` |
| Patient | `pat_zara`, `pat_omar` | `patient123` |

Change or delete these before any real use.

## Switching to RDS and S3

Everything is set by environment variables (see `.env.example`):

| Variable | Effect |
|---|---|
| `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | With `DB_HOST` set the app uses PostgreSQL on RDS. Empty means SQLite. |
| `USE_S3=True`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME` | Uploaded files go to S3. |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SEED_DEMO` | First run setup on a deployment. |
| `TIME_ZONE`, `CURRENCY`, `CLINIC_NAME` | Display settings. |

Run `python manage.py check_aws` any time to test the database and storage connection. It explains what to fix.

Then follow **docs/AWS_SETUP.md** for the complete EC2 and Elastic Beanstalk walkthrough.

## Suggested demo script

1. **Admin** (`clinic_admin`): Admin panel > Add staff or doctor. Create a doctor. You land on their working hours page, add hours.
2. **Patient** (register a new account or use `pat_omar`): fill in the health profile, Book > choose a doctor and date > pick a free time. Upload a lab report.
3. **Front desk** (`desk`): register a walk-in patient, book for them, see today's schedule. Try opening a medical record: it is hidden from this role.
4. **Doctor** (`dr_amina`): Today > Start consultation, enter vitals and diagnosis, add prescriptions, print the summary.
5. **Front desk**: the visit appears under "Visits waiting for an invoice". Create the invoice, record a partial cash payment.
6. **Patient**: open Invoices, pay the balance online (simulated), print the invoice.
7. **Admin**: Overview shows revenue and appointment charts. Infrastructure shows RDS and S3 in use and runs a live storage test.

## Tests

```bash
python manage.py test
```

18 end to end tests cover registration, role protection, slot generation, double booking prevention, cancellation,
consultations and prescriptions, privacy rules, lab report upload and download, invoices, partial and online payments,
admin tools and the deployment checks.

## Project layout

```
config/          settings (env driven), urls, wsgi, template context
accounts/        user model with roles, login, registration, profile
clinic/          doctors, specialties, schedules, patient profiles, patient pages
appointments/    appointments, free slot calculation, booking, cancel, no show
records/         consultations, prescriptions, lab reports (S3)
billing/         invoices, items, payments
dashboard/       home, dashboards, admin panel, infrastructure page, seed/bootstrap/check_aws commands, tests
templates/       all HTML
static/css/      hand written stylesheet (no framework, no external fonts)
deploy/ec2/      setup.sh, gunicorn systemd unit, nginx config
deploy/aws/      s3-policy.json, ec2-trust-policy.json
deploy/beanstalk/make_bundle.py   builds caredesk-eb.zip
.ebextensions/   Beanstalk hooks (check_aws, migrate, collectstatic, bootstrap)
.platform/       Beanstalk nginx upload limits
Procfile         Beanstalk process command
docs/            AWS_SETUP.md, ARCHITECTURE.md (modules, permissions, ER diagram)
```

## Health check

`GET /health/` returns `ok` when the app can reach its database.
