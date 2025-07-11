import shutil
import sys
import os
from pathlib import Path
from query_engine_client import QueryEngineClient
from container_params import ContainerParams, ContainerParamError
from pii_anonymization_pipeline import create_pipeline_from_config, create_default_pipeline

def execute_query(params: ContainerParams) -> bool:
    """Execute the query using the query engine client.
    
    Args:
        params: Container parameters with query details
        
    Returns:
        True if query execution was successful, False otherwise
    """
    if not params.validate_production_mode():
        return False
        
    # Initialize query engine client
    query_engine_client = QueryEngineClient(
        params.query, 
        params.query_signature, 
        str(params.db_path)
    )
    
    # Execute query
    print(f"Executing query: {params.query}")
    query_result = query_engine_client.execute_query(
        params.compute_job_id, 
        params.data_refiner_id,
        params.query_params
    )
    
    if not query_result.success:
        print(f"Error executing query: {query_result.error}")
        return False
        
    print(f"Query executed successfully, processing results from {params.db_path}")
    return True


def process_query_results(params: ContainerParams) -> bool:
    """Process query results with PII anonymization.
    
    Args:
        params: Container parameters with database paths and configuration
        
    Returns:
        True if processing was successful, False otherwise
    """
    try:
        # Get configuration path from environment or use default
        config_path = os.getenv("PRESIDIO_CONFIG_PATH", "/app/config/presidio_config.json")
        
        # Determine output database path
        output_db_path = params.output_path / "query_results.db"
        
        # Create PII anonymization pipeline
        if Path(config_path).exists():
            print(f"Loading Presidio configuration from: {config_path}")
            pipeline = create_pipeline_from_config(
                config_path=Path(config_path),
                input_db_path=params.db_path,
                output_db_path=output_db_path
            )
        else:
            print("Using default Presidio configuration")
            pipeline = create_default_pipeline(
                input_db_path=params.db_path,
                output_db_path=output_db_path
            )
        
        # Validate pipeline configuration
        if not pipeline.validate_configuration():
            print("Error: Pipeline configuration validation failed")
            return False
        
        # Process the database
        print("Starting PII anonymization processing...")
        processing_stats, anonymization_stats = pipeline.process_database()
        
        # Save anonymization report
        report_path = params.output_path / "anonymization_report.json"
        pipeline.save_anonymization_report(report_path)
        
        # Log processing results
        print(f"Processing completed successfully:")
        print(f"  - Tables processed: {processing_stats.processed_tables}")
        print(f"  - Rows processed: {processing_stats.processed_rows:,}")
        print(f"  - Rows anonymized: {processing_stats.anonymized_rows:,}")
        print(f"  - Processing time: {processing_stats.get_elapsed_time():.2f} seconds")
        print(f"  - Processing rate: {processing_stats.get_rows_per_second():.2f} rows/second")
        print(f"  - Values anonymized: {anonymization_stats.total_values_anonymized:,}")
        
        if anonymization_stats.entities_found:
            print("  - PII entities found:")
            for entity_type, count in anonymization_stats.entities_found.items():
                print(f"    - {entity_type}: {count}")
        
        print(f"Anonymization report saved to: {report_path}")
        
        return True
        
    except Exception as e:
        print(f"Error processing query results: {e}")
        return False

def main() -> None:
    """Main entry point for the worker."""
    try:
        # Load parameters from environment variables
        try:
            params = ContainerParams.from_env()
        except ContainerParamError as e:
            print(f"Error in container parameters: {e}")
            sys.exit(1)
        
        # Handle development vs production mode
        if params.dev_mode:
            print("Running in DEVELOPMENT MODE - using local database file")
            print(f"Processing query results from {params.db_path}")
        else:
            # In production mode, execute the query first
            if not execute_query(params):
                sys.exit(2)
        
        # Process query results with PII anonymization
        if not process_query_results(params):
            sys.exit(3)
        
    except Exception as e:
        print(f"Error in worker execution: {e}")
        sys.exit(4)

if __name__ == "__main__":
    main()