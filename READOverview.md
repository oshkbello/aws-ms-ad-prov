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

### **Problem We’re Seeing**

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

### **Additional Context**

* The VPC and IAM roles are created and configured from Account A into Account B before provisioning.
* The `PlatformSupportRole` in Account B is assumed by the Lambda in Account A.
* S3 permissions for the template have worked in past runs; the failure only occurs in the directory creation phase.

---
---

