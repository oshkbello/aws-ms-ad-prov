Architecture Overview (Multi-Account Setup)

We are working across two AWS accounts:

* **Account A (Platform account)** → runs central orchestration
* **Account B (Business account)** → hosts the actual provisioned resources

Here’s how the setup is structured:

---

1. **Account A → Lambda #1: VPC provisioning**

   * Deploys the VPC, subnets, and security groups in **Account B** via CloudFormation.
   * Produces:

     * VPC ID
     * Directory Subnet A + B IDs (in separate AZs)

---

2. **Account A → Lambda #2: AD provisioning (`CreateADStackLambda`)**

   * Assumes `PlatformSupportRole` in **Account B**.
   * Runs:

     * VPC DNS + subnet validation
     * Secrets Manager admin password validation
     * Directory quota check
   * Calls **CloudFormation in Account B** to create the AWS Managed Microsoft AD.

---

3. **Account B → Resources**

   * VPC, subnets, and security groups (from Lambda #1).
   * Secrets Manager secret for AD admin password.
   * `PlatformSupportRole` IAM role with:

     ```
     sts:AssumeRole, ec2:*, cloudformation:*, ds:*, secretsmanager:*
     ```

---

### ⚠️ **Problem We’re Seeing**

When the **CreateADStackLambda** in Account A runs to launch the AWS Managed Microsoft AD in Account B, it consistently fails at the CloudFormation phase with:

```
Reason: An internal service error has been encountered during directory creation.
```

Details:

* All **prechecks succeed**:

  * Secret exists in Secrets Manager (Account B).
  * VPC DNS support + hostnames are enabled.
  * Subnets are validated and in separate AZs.
  * There are ≥ 250 available IPs in each subnet.
  * We are within AD directory quotas.
* The Lambda successfully assumes the cross-account role and calls `cloudformation.create_stack()`.
* The directory shows up in AWS Directory Service in Account B, but its **status immediately moves to `Failed`** with an internal service error.

---

### 💥 **Suspected Causes**

We suspect the failure is happening **inside the AWS Managed Microsoft AD service itself in Account B** due to one or more of the following:

* Misconfiguration in the CloudFormation template (`microsoft-ad-template.yaml`).
* Additional service prerequisites (beyond DNS, subnets, and secrets) that we are missing.
* Region-specific quota or feature limits.
* Sizing, subnet range, or IP availability edge cases.
* A backend AWS-side issue or known defect.

---

### 🧪 **How to Reproduce / Test**

1. Upload the AD CloudFormation template to Account A S3 bucket:

   ```
   s3://cf-templates-1gxf2an4sweo5-ca-central-1/microsoft-ad-template.yaml
   ```

2. Run the `CreateADStackLambda` in Account A with this event:

   ```json
   {
     "businessId": "testco002",
     "awsAccountId": "<Account B AWS ID>",
     "VpcId": "vpc-020dfdf85a8806413",
     "DirectorySubnetA": "subnet-0b5ed818bceeb9b3d",
     "DirectorySubnetB": "subnet-0a6a382d6867a30de"
   }
   ```

3. Watch **CloudWatch Logs** in Account A:

   * Prechecks → expect ✅
   * Stack creation → hits internal service error

4. Observe Account B → AWS Directory Service console:

   * Directory is created
   * Status moves to `Failed` with **internal error**

---

### 📂 **Relevant Files Provided**

✅ CloudFormation template (`microsoft-ad-template.yaml`)
✅ AD provisioning Lambda code (`CreateADStackLambda`)

---

### 💬 **Additional Context**

* The VPC and IAM roles are created and configured from Account A into Account B before provisioning.
* The `PlatformSupportRole` in Account B is assumed by the Lambda in Account A.
* S3 permissions for the template have worked in past runs; the failure only occurs in the directory creation phase.

---

### ✅ Request

We need your help to:

* Identify why AWS Managed Microsoft AD consistently fails with an internal error during directory creation in Account B.
* Confirm whether the template or configuration needs adjustments.
* Check for any known AWS service-side issues or required quota increases.
* Recommend any additional steps or architecture changes.

---

Please let me know if you need the VPC template, IAM role template, or CloudFormation stack outputs — I can send those over as well.

Thank you for your help!

---

✅ If you want, I can also draft this as:

* A formal AWS Support ticket
* A Slack or email message
* A checklist of test artifacts to attach

Would you like me to prep one of those for you? 🚀 Let me know!


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

