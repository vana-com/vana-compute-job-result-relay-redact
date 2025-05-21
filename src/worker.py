import shutil
import sys
from query_engine_client import QueryEngineClient
from container_params import ContainerParams, ContainerParamError

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
        
        shutil.copy(params.db_path, params.input_path)
        
    except Exception as e:
        print(f"Error in worker execution: {e}")
        sys.exit(3)

if __name__ == "__main__":
    main()