# AWS setup and deployment guide

You deploy the same code twice: once by hand on **EC2**, once with **Elastic Beanstalk**.
Both use the same **RDS PostgreSQL** database and the same **S3** bucket, which lets you show that
data and files live in AWS services and not on the web servers.

```
Browser --> EC2 (Nginx + Gunicorn + Django)  --\
                                                 +--> RDS PostgreSQL  (all records)
Browser --> Elastic Beanstalk (same code)    --/ +--> S3 bucket       (lab reports, photos)
```

Use one AWS region for everything (examples use `us-east-1`, use your own region everywhere).

The most common first-deploy failures are **security groups** (database timeout) and a **missing IAM role**
(NoCredentialsError). Steps 1 and 4 prevent both, and the installer runs a pre-flight check
(`python manage.py check_aws`) that tells you which one is wrong and how to fix it.

---------------------------------------------------------------------------

## 1. Security groups (EC2 console > Security Groups > Create)

| Name | Inbound rules |
|---|---|
| `caredesk-web-sg` | HTTP 80 from Anywhere (0.0.0.0/0), SSH 22 from My IP |
| `caredesk-rds-sg` | PostgreSQL 5432 with **source = `caredesk-web-sg`** (choose the group in the Source box, do not type an IP) |

Attach `caredesk-web-sg` to the EC2 instance (step 5) **and** to the Beanstalk instances (step 6). Because the
database rule trusts that group, both servers can reach RDS with no extra rules.

Already launched an instance with a different group (for example `launch-wizard-1`)? Either:

* **Change the instance's group:** EC2 > Instances > select > Actions > Security > Change security groups.
* **Or edit the RDS rule:** add inbound PostgreSQL 5432 with the source set to the instance's current group.
* **Or let AWS do it:** RDS > your database > Actions > **Set up EC2 connection** > pick the instance.

## 2. RDS PostgreSQL

1. RDS > Create database > **Standard create** > **PostgreSQL**.
2. Template **Free tier** (or Dev/Test). Instance class `db.t3.micro`, 20 GB storage.
3. DB instance identifier `caredesk-db`. Master username `caredeskadmin`. Choose a password and save it.
4. Connectivity: default VPC, **Public access: No**, security group `caredesk-rds-sg`.
5. Additional configuration > **Initial database name: `caredesk`**.
6. Create. When the status is *Available*, copy the **Endpoint**
   (looks like `caredesk-db.abc123.us-east-1.rds.amazonaws.com`).

## 3. S3 bucket

1. S3 > Create bucket. The name must be unique, for example `caredesk-yourname-files`. Same region as RDS.
2. Leave **Block all public access ON**. The app creates temporary signed links, so nothing is public, and you
   need no bucket policy and no CORS.
3. Create.

## 4. IAM: permission for S3 without access keys

1. IAM > Policies > Create policy > **JSON**. Paste the content of `deploy/aws/s3-policy.json`, replace
   `YOUR-BUCKET-NAME` in both places, name it `CareDeskS3Access`.
2. **For EC2:** IAM > Roles > Create role > AWS service > **EC2** > attach `CareDeskS3Access` > name it
   `caredesk-ec2-role`.
3. **For Beanstalk:** IAM > Roles > open `aws-elasticbeanstalk-ec2-role` > Add permissions > attach
   `CareDeskS3Access`. (This role is created the first time you make a Beanstalk environment. If it does not exist
   yet, create it with the same steps as step 2 and the managed policy `AWSElasticBeanstalkWebTier`.)

The bucket name in the policy must match `AWS_STORAGE_BUCKET_NAME` exactly.

---------------------------------------------------------------------------

## 5. Deployment A: EC2 (manual)

### Launch the instance

1. EC2 > Launch instance. Name `caredesk-ec2`. AMI **Ubuntu Server 24.04 LTS** (newer Ubuntu releases also work).
   Type `t3.micro` or `t2.micro`.
2. Create or pick a key pair (`.pem` file).
3. Network settings: default VPC, **Auto-assign public IP: Enable**, security group `caredesk-web-sg`.
4. Advanced details > **IAM instance profile: `caredesk-ec2-role`**. (Forgot? Fix later with Actions > Security >
   **Modify IAM role**. It takes effect at once.)
5. Storage 15 GB. Launch.

### Copy the project and install

From your computer:

```bash
scp -i your-key.pem caredesk.zip ubuntu@<EC2-PUBLIC-IP>:~
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>
```

On the server:

```bash
sudo apt-get update && sudo apt-get install -y unzip
unzip caredesk.zip && cd caredesk
cp .env.example .env
nano .env
```

Set these values in `.env`:

```
SECRET_KEY=<paste a long random string>
DEBUG=False
ALLOWED_HOSTS=*
DB_HOST=caredesk-db.abc123.us-east-1.rds.amazonaws.com
DB_NAME=caredesk
DB_USER=caredeskadmin
DB_PASSWORD=<your rds password>
USE_S3=True
AWS_STORAGE_BUCKET_NAME=caredesk-yourname-files
AWS_S3_REGION_NAME=us-east-1
ADMIN_USERNAME=myadmin
ADMIN_PASSWORD=<choose one>
SEED_DEMO=True
TIME_ZONE=Asia/Karachi
CURRENCY=Rs
```

* Leave `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` **empty**. The instance role is used.
* `AWS_S3_REGION_NAME` must be the region where the bucket really is.
* `ADMIN_USERNAME` must **not** be a demo name (`clinic_admin`, `desk`, `dr_amina`, `dr_bilal`, `dr_chen`,
  `pat_zara`, `pat_omar`).
* `TIME_ZONE` makes appointment times match your clock. Use any name from the tz database (for example
  `Europe/London`, `America/New_York`). `CURRENCY` is only the symbol shown next to prices.
* Generate a secret key with: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`

Then run:

```bash
bash deploy/ec2/setup.sh
```

The script installs Python, Nginx and Gunicorn, **checks that RDS and S3 are reachable**, runs migrations, creates
the admin and demo data, and starts the app as a `systemd` service.

If the check fails it stops and prints what to fix. Fix it, then run the same command again. The script is safe to
repeat.

Open `http://<EC2-PUBLIC-IP>/` (use http, not https). Log in with your `ADMIN_USERNAME`, open
**Admin panel > Infrastructure** and press **Run storage test**.

Useful commands:

```bash
sudo systemctl status caredesk          # is the app running
sudo journalctl -u caredesk -f          # live app logs
sudo tail -f /var/log/nginx/error.log   # Nginx errors
cd /opt/caredesk && ./venv/bin/python manage.py check_aws    # re-run the pre-flight check
```

New version: upload the new zip, unzip over the folder, keep your `.env`, run `bash deploy/ec2/setup.sh` again.

### Stopping the instance to save credits

* Stopping is safe. The app starts again on its own after boot. Your data is in RDS and S3.
* The public IP **changes** on every start. Copy the new one from the EC2 console.
* Stopped EC2 is not billed for compute, but **RDS keeps billing**. Stop it too (RDS > Actions > Stop temporarily).
  AWS restarts a stopped RDS automatically after 7 days.
* Start RDS first and wait for *Available*, then start EC2. If the site shows an error, run
  `sudo systemctl restart caredesk`.
* Beanstalk cannot be paused. Terminate the environment when you are not using it and recreate it from the zip later.

---------------------------------------------------------------------------

## 6. Deployment B: Elastic Beanstalk

### Build the bundle

On your computer, inside the project folder:

```bash
python deploy/beanstalk/make_bundle.py
```

This creates `caredesk-eb.zip` with `manage.py`, `Procfile`, `.ebextensions` and `.platform` at the **top level**
of the zip, which Beanstalk requires. Do not zip the folder by hand.

### Create the environment

1. Elastic Beanstalk > Create application. Name `caredesk`.
2. Environment tier **Web server environment**.
3. Platform **Python**, newest **Python 3.11 or 3.12 on Amazon Linux 2023**.
4. Application code: **Upload your code** > choose `caredesk-eb.zip`.
5. Presets: **Single instance (free tier eligible)**. Next.
6. Service access: create or pick a service role. EC2 instance profile **`aws-elasticbeanstalk-ec2-role`** (the one
   you gave S3 access in step 4). Next.
7. Networking: default VPC, **Public IP address: Activate**, select the subnets. Do **not** add a database here,
   you already have RDS. Next.
8. Instance traffic and scaling: under EC2 security groups pick **`caredesk-web-sg`** so the instance can reach RDS. Next.
9. Updates, monitoring and logging: defaults are fine. Under **Environment properties** add:

| Name | Value |
|---|---|
| `SECRET_KEY` | a long random string |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `*` |
| `DB_HOST` | your RDS endpoint |
| `DB_NAME` | `caredesk` |
| `DB_USER` | `caredeskadmin` |
| `DB_PASSWORD` | your RDS password |
| `USE_S3` | `True` |
| `AWS_STORAGE_BUCKET_NAME` | your bucket name |
| `AWS_S3_REGION_NAME` | your region |
| `ADMIN_USERNAME` | a name that is not a demo username |
| `ADMIN_PASSWORD` | choose one |
| `SEED_DEMO` | `True` (skipped automatically if the EC2 deployment already loaded it into the same database) |
| `TIME_ZONE` | for example `Asia/Karachi` |
| `CURRENCY` | for example `Rs` |

10. Submit. After about 5 minutes the environment turns green. Open its URL.

On every deployment `.ebextensions/01_django.config` runs `check_aws`, `migrate`, `collectstatic` and `bootstrap`.
If the pre-flight check fails the deployment stops and the reason is in **Logs > Request logs > `eb-engine.log`**.

To redeploy: environment page > **Upload and deploy** with a new `caredesk-eb.zip`.

### Same data or separate data?

* Same `DB_NAME` for both deployments: both sites show the same patients and appointments. Best for a demo.
* Different names (create the second with `CREATE DATABASE caredesk_eb;`): two independent sites.

---------------------------------------------------------------------------

## 7. Prove it works (for your report)

1. **Admin panel > Infrastructure** shows `PostgreSQL (Amazon RDS)` with your endpoint and `Amazon S3` with your
   bucket. **Run storage test** should say *Storage works*.
2. Log in as a patient and upload a lab report. In the S3 console open the bucket: the file is under `lab_reports/`.
3. Check the records in RDS from the EC2 instance:

```bash
sudo apt-get install -y postgresql-client
psql -h <RDS-ENDPOINT> -U caredeskadmin -d caredesk -c "\dt"
psql -h <RDS-ENDPOINT> -U caredeskadmin -d caredesk -c "select username, role from accounts_user;"
```

4. Stop and start the app server: the data and files are still there, because they live in RDS and S3.

## 8. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `check_aws` says **timeout expired** to the database | The network blocks port 5432. Do step 1: RDS security group must allow PostgreSQL 5432 from the server's security group. Same VPC for both. |
| `password authentication failed` | Wrong `DB_USER` or `DB_PASSWORD`. |
| `database "caredesk" does not exist` | You skipped the initial database name. Run `CREATE DATABASE caredesk;` with psql. |
| `connection refused` | RDS is stopped or still starting. Wait for *Available*. |
| **NoCredentialsError** | The server has no IAM role. EC2 > Actions > Security > Modify IAM role > `caredesk-ec2-role`. |
| **AccessDenied** on S3 | The role lacks `CareDeskS3Access`, or the bucket name inside the policy differs from `AWS_STORAGE_BUCKET_NAME`. |
| Bucket **301 / PermanentRedirect** | `AWS_S3_REGION_NAME` is not the bucket's region. |
| Appointment times look hours off | Set `TIME_ZONE` in `.env`, restart: `sudo systemctl restart caredesk`. |
| Login form gives 403 CSRF on a domain or HTTPS | Set `CSRF_TRUSTED_ORIGINS=https://your-domain`. |
| `413 Request Entity Too Large` | Nginx upload limit (200 MB in the provided configs). Restart Nginx after edits. |
| Beanstalk Severe or 502 | Console > Logs > Request logs. Read `eb-engine.log` (deploy errors) and `web.stdout.log` (app errors). |
| No styling | `collectstatic` did not run. On EC2: `cd /opt/caredesk && ./venv/bin/python manage.py collectstatic --noinput`. |
| "Demo data is already present" | Normal. The demo is loaded once per database. |

## 9. Clean up to avoid charges

Terminate the Beanstalk environment, terminate the EC2 instance, delete the RDS instance (skip the final snapshot if
you do not need it), empty and delete the S3 bucket, and release any Elastic IP.

## 10. HTTPS (optional)

Not needed for the assignment. With a domain pointed at the EC2 IP:
`sudo apt-get install -y certbot python3-certbot-nginx && sudo certbot --nginx -d your-domain`, then set
`CSRF_TRUSTED_ORIGINS=https://your-domain` in `.env` and run `sudo systemctl restart caredesk`.

## Privacy note

This is a learning project with demo data. Do not enter real patient information. A real clinic system needs
encryption policies, audit logs and legal review that are outside this assignment.
