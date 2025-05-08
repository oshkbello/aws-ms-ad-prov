Architecture Overview

We’ve automated the provisioning of AWS Managed Microsoft AD using a series of Lambda functions and CloudFormation templates.

Components involved:

1. VPC provisioning Lambda

   * Creates the VPC, subnets, and security groups via a CloudFormation template.
   * Ensures two directory subnets (in separate AZs) are ready for AD.

2. IAM permissions (`PlatformSupportRole`)

   * Deployed via its own CloudFormation template.
   * Grants the needed permissions:

     ```
     sts:AssumeRole, ec2:*, cloudformation:*, ds:*, secretsmanager:*
     ```
   * The AD provisioning Lambda (`CreateADStackLambda`) assumes this role.

3. AD provisioning Lambda (`CreateADStackLambda`)

   * Runs prechecks:

     * Validates VPC DNS settings and subnets.
     * Checks Secrets Manager for the AD admin password.
     * Confirms quota limits on AD.
   * Generates a presigned S3 URL to the AD CloudFormation template.
   * Calls `cloudformation.create_stack()` to launch the AWS Managed Microsoft AD directory.

---

### Problem We’re Seeing

When the AD provisioning Lambda calls `create_stack()` to launch the AWS Managed Microsoft AD, the stack consistently fails with an internal service error.

Specifically:

* CloudFormation reports:

  ```
  Reason: An internal service error has been encountered during directory creation.
  ```
* The directory in AWS Directory Service stays in the `Failed` state.
* We are within quota limits.
* The Lambda has successfully validated:
  * VPC ID and DNS settings (`enableDnsSupport`, `enableDnsHostnames`)
  * Subnet IDs and availability zones
  * Secrets Manager admin password
* We are passing the correct VPC, subnets, and secret to the stack.



### Additional Context

* We have another Lambda provisioning the VPC and subnets via template.
* The `PlatformSupportRole` is deployed via template and provides all needed permissions.
* The failure consistently occurs inside the Managed Microsoft AD service, not in the Lambda or CloudFormation control plane.

---

