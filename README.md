# Vana PII Anonymization Compute Job

This is a **privacy-preserving compute job** that automatically detects and anonymizes personally identifiable information (PII) in query results using Microsoft Presidio. Designed for Vana's Trusted Execution Environment (TEE) infrastructure, it ensures sensitive data is protected while maintaining analytical value.

**🔒 Privacy-First Processing**: Processes query results through a comprehensive PII anonymization pipeline, ensuring sensitive data never leaves the compute environment in raw form. Perfect for DataDAOs requiring GDPR, HIPAA, or other privacy compliance.

## What This Compute Job Does

🎯 **Core Function**: Transforms sensitive query results into privacy-compliant datasets through automated PII detection and anonymization.

**Processing Pipeline**:
1. **Receives** query results from Vana Query Engine at `/mnt/input/query_results.db`
2. **Analyzes** data using Microsoft Presidio + custom recognizers to detect PII entities
3. **Anonymizes** sensitive information using configurable strategies (masking, redaction, replacement)  
4. **Outputs** privacy-protected database to `/mnt/output/query_results.db` + detailed anonymization report

**Real-World Impact**: Enables safe data sharing and analysis while protecting individual privacy and ensuring regulatory compliance.

## PII Anonymization Features

### 🔍 **Comprehensive PII Detection**
**Supported Entity Types:**
- 👤 **Person Names**: `John Smith` → `Jo** Sm***` (custom masking)
- 📧 **Email Addresses**: `user@example.com` → `us***@e***.com` (custom masking)  
- 📞 **Phone Numbers**: `(555) 123-4567` → `(***) ***-4567` (mask ending)
- 💳 **Credit Cards**: `4532-1234-5678-9012` → `4532-12************` (secure masking)
- 🏠 **Addresses**: `123 Main St, New York` → `1** M*** St, N** Y***` (location masking)
- 🆔 **SSNs**: `123-45-6789` → *[completely redacted]* (full removal)
- 🌐 **IP Addresses**: `192.168.1.1` → `192.***.***.***` (network masking)
- 🔗 **URLs**: Personal website links masked to protect identity

## Quick Start

1. **Prepare Test Data**: Edit `dummy_data.sql` with realistic PII data to test anonymization
2. **Generate Database**: Run `sqlite3 ./input/query_results.db < dummy_data.sql`
3. **Configure Anonymization**: Customize `config/presidio_config.json` for your PII detection needs
4. **Test Locally**: Run `./scripts/image-build.sh && ./scripts/image-run.sh` with `DEV_MODE=1`
5. **Review Results**: Check `/mnt/output/query_results.db` for anonymized data and `anonymization_report.json` for statistics
6. **Deploy**: Export with `./scripts/image-export.sh` and submit through Vana app for DLP approval

## Development vs Production Mode

The worker supports two modes of operation:

- **Development Mode**: Set `DEV_MODE=1` to test PII anonymization on local databases without connecting to the query engine.
  ```bash
  # Example: Test anonymization locally
  docker run -e DEV_MODE=1 \
    -v /local/path/to/input:/mnt/input \
    -v /local/path/to/output:/mnt/output \
    my-compute-job
  # Check anonymized results in output/query_results.db and anonymization_report.json
  ```

- **Production Mode**: Connects to Vana Query Engine, receives query results, and applies PII anonymization before output.
  ```bash
  # Example: Production anonymization pipeline  
  docker run -e QUERY="SELECT user_id, name, email, address FROM users" \
    -e QUERY_SIGNATURE="xyz123" \
    -e QUERY_ENGINE_URL="https://query.vana.org" \
    -v /local/path/to/output:/mnt/output \
    my-compute-job
  # Outputs privacy-compliant anonymized data automatically
  ```

## Platform Compatibility

**Important**: Docker images must be compatible with AMD architecture to run properly in the Compute Engine's Trusted Execution Environments (TEEs). When building your Docker image:

- Ensure all dependencies and binaries are AMD64-compatible
- Build the Docker image on an AMD64 platform or use the `--platform=linux/amd64` flag with Docker buildx
- Test the image in an AMD64 environment before submission
- Avoid using architecture-specific binaries or libraries when possible

## Utility scripts

These are sugar scripts for docker commands to build, export, and run the worker image consistently for simpler dev cycles / iteration.

The `image-export.sh` script builds an exportable `.tar` for uploading in remote services for registering with the compute engine / image registry contracts.

## Generating test data

The script `dummy_data.sql` should include **realistic PII data** to properly test the anonymization pipeline. Add various types of sensitive information:

```sql
-- Include test data with PII for anonymization testing
INSERT INTO users VALUES 
  ('u001', 'john.doe@example.com', 'John Smith', '(555) 123-4567', 
   '123 Main St, New York, NY', '123-45-6789', '4532-1234-5678-9012'),
  ('u002', 'jane.smith@test.com', 'Jane Doe', '+1-555-987-6543',
   '456 Oak Ave, Los Angeles, CA', '987-65-4321', '5555-4444-3333-2222');
```

To transform this test data: `sqlite3 ./input/query_results.db < dummy_data.sql`

**🔒 Privacy Note**: The anonymization pipeline will automatically detect and protect all PII entities in your test data, demonstrating real-world privacy protection capabilities.

## Building a Compute Job

- Compute Jobs are run as Docker containers inside of the Compute Engine TEE.
- Docker container images ("Compute Instructions") must be approved for a given Data Refiner id by DLP owners through the Compute Instruction Registry smart contract before being submitted for processing via the Compute Engine API.
- The Data Refiner id determines the schema that can be queried against, the granted permissions by the DLP owner, and the cost to access each queried data component (schema, table, column) of the query when running compute jobs.
- Individual queries to the Query Engine are run outside of the Compute Job by the Compute Engine directly before invoking the Compute Job.
- Input data is provided from the compute engine to the compute job container through a mounted `/mnt/input` directory.
  - This directory contains a single `query_results.db` SQLite file downloaded from the Query Engine after a query has been successfully processed.
  - A queryable `results` table is the only table in the mounted `query_results.db`. This table contains all of the queried data points of the query submitted to the Query Engine through the Compute Engine API.
  - *Example with PII Anonymization:*
```sql
-- Refiner Schema:
CREATE TABLE users (id TEXT, name TEXT, email TEXT, address TEXT, ssn TEXT);

-- Application Builder Query:
SELECT id, name, email, address FROM users;

-- Query Engine outputs raw `query_results.db`:
CREATE TABLE results (id TEXT, name TEXT, email TEXT, address TEXT);
-- Raw data: ('u001', 'John Smith', 'john@example.com', '123 Main St')

-- PII Anonymization Compute Job Processing:
-- 🔍 Detects: PERSON, EMAIL_ADDRESS, LOCATION entities
-- 🛡️ Anonymizes: names, emails, addresses automatically
-- ✅ Preserves: user IDs and analytical structure

-- Final anonymized output:
-- ('u001', 'Jo** Sm***', 'jo***@e***.com', '1** M*** St')
```
- Output data Artifacts are provided to the Compute Engine from the Compute Job container through a mounted `/mnt/output` directory.
- Any Artifact files generated in this directory by the Compute Job will later be available for consumption and download by the job owner (=application builder) through the Compute Engine API.

### PII Anonymization Workflow

1. **Query Ingestion**: Read raw query results from `/mnt/input/query_results.db`
2. **PII Detection**: Analyze each data field using Microsoft Presidio + custom recognizers
3. **Smart Anonymization**: Apply configured strategies while preserving analytical value:
   - Person names → Custom partial masking (`John Smith` → `Jo** Sm***`)
   - Emails → Domain-preserving masking (`user@example.com` → `us***@e***.com`)
   - Credit cards → Secure prefix preservation (`4532-1234-5678-9012` → `4532-12************`)
   - Addresses → Structure-preserving location masking
   - SSNs → Complete redaction for maximum security
4. **Privacy-Compliant Output**: Write anonymized database + comprehensive anonymization report

## Technical Architecture

### 🔬 **Microsoft Presidio Integration**
- **NLP-Based Detection**: Uses spaCy `en_core_web_sm` model for context-aware PII identification
- **Custom Recognizers**: Enhanced regex patterns for financial data and addresses
- **Configurable Confidence**: Tunable thresholds (0.6-0.9) for precision/recall balance
- **Multi-Language Support**: Extensible for international privacy compliance

### Submitting Compute Instructions For DLP Approval

1. Build and export the Compute Job Docker image to a `.tar`, and `gzip` to a `.tar.gz`.
2. Upload it to a publicly accessible URL for later retrieval by the Compute Engine.
3. Calculate the SHA256 checksum of the image archive file and document for use in on-chain registration. (*Example:* `sha256sum my-compute-job.tar.gz | cut -d' ' -f1`)
4. Write the Compute Instruction on-chain to the ComputeInstructionRegistry smart contract via the `addComputeInstruction` function with both the publicly available image URL and the SHA256 image checksum.
5. Notify the relevant DLP owner for Compute Instruction image audits and eventual approval with the DLP owner wallet through the `updateComputeInstruction` ComputeInstructionRegistry smart contract function.
6. Approval can be checked and verified on-chain with the `isApproved` ComputeInstructionRegistry smart contract function.