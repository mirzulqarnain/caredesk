s3-policy.json        Permission policy for the bucket. Replace YOUR-BUCKET-NAME (two places),
                      then IAM > Policies > Create policy > JSON > paste it. Name it CareDeskS3Access.
ec2-trust-policy.json Trust policy that lets EC2 use an IAM role. Only needed if you create the
                      role from the CLI or the JSON tab. The console does this for you when you pick
                      AWS service > EC2.

Attach CareDeskS3Access to:
  1. your EC2 role (caredesk-ec2-role)
  2. aws-elasticbeanstalk-ec2-role (used by Elastic Beanstalk)

Then attach the EC2 role to the instance:
  EC2 console > select instance > Actions > Security > Modify IAM role.

CLI alternative:
  aws iam create-policy --policy-name CareDeskS3Access --policy-document file://deploy/aws/s3-policy.json
