"""
SQLite streaming processor for handling large query result databases.

This module provides memory-efficient streaming processing of SQLite databases,
allowing for processing of databases that are too large to fit in memory.
It supports:
- Streaming reads from SQLite databases
- Batch processing of rows
- Dynamic table schema discovery
- Memory-efficient processing for large datasets (10GB+)
- Streaming writes to output database
"""

import sqlite3
import logging
import time
from typing import Dict, List, Tuple, Any, Optional, Iterator, Callable
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


logger = logging.getLogger(__name__)


@dataclass
class TableInfo:
    """Information about a SQLite table."""
    name: str
    columns: List[str]
    column_types: Dict[str, str]
    row_count: int
    primary_key: Optional[str] = None


@dataclass
class ProcessingStats:
    """Statistics for database processing."""
    total_tables: int = 0
    processed_tables: int = 0
    total_rows: int = 0
    processed_rows: int = 0
    anonymized_rows: int = 0
    start_time: float = 0
    end_time: Optional[float] = None
    
    def get_elapsed_time(self) -> float:
        """Get elapsed processing time."""
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time
    
    def get_rows_per_second(self) -> float:
        """Get processing rate in rows per second."""
        elapsed = self.get_elapsed_time()
        return self.processed_rows / elapsed if elapsed > 0 else 0


class SQLiteStreamProcessor:
    """
    Memory-efficient SQLite database processor for large datasets.
    
    This class provides streaming processing capabilities for SQLite databases,
    allowing processing of databases that exceed available memory.
    """
    
    def __init__(self, 
                 input_db_path: Path,
                 output_db_path: Path,
                 batch_size: int = 1000,
                 max_memory_mb: int = 512,
                 enable_parallel_processing: bool = True,
                 num_workers: int = 4):
        """
        Initialize the SQLite stream processor.
        
        Args:
            input_db_path: Path to input SQLite database
            output_db_path: Path to output SQLite database
            batch_size: Number of rows to process in each batch
            max_memory_mb: Maximum memory usage in MB
            enable_parallel_processing: Whether to enable parallel processing
            num_workers: Number of worker threads for parallel processing
        """
        self.input_db_path = Path(input_db_path)
        self.output_db_path = Path(output_db_path)
        self.batch_size = batch_size
        self.max_memory_mb = max_memory_mb
        self.enable_parallel_processing = enable_parallel_processing
        self.num_workers = num_workers
        
        self.stats = ProcessingStats()
        self.table_info_cache: Dict[str, TableInfo] = {}
        self._setup_logging()
        
        # Ensure output directory exists
        self.output_db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def get_table_info(self, table_name: str) -> TableInfo:
        """
        Get information about a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            TableInfo object with table metadata
        """
        if table_name in self.table_info_cache:
            return self.table_info_cache[table_name]
        
        with sqlite3.connect(str(self.input_db_path)) as conn:
            cursor = conn.cursor()
            
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = cursor.fetchall()
            
            logger.debug(f"Table {table_name} PRAGMA table_info result: {columns_info}")
            
            columns = []
            column_types = {}
            primary_key = None
            
            for col_info in columns_info:
                col_name = col_info[1]
                col_type = col_info[2]
                is_pk = col_info[5]
                
                columns.append(col_name)
                column_types[col_name] = col_type
                
                if is_pk:
                    primary_key = col_name
            
            logger.info(f"Table {table_name} detected columns: {columns}")
            logger.info(f"Table {table_name} column types: {column_types}")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            
            table_info = TableInfo(
                name=table_name,
                columns=columns,
                column_types=column_types,
                row_count=row_count,
                primary_key=primary_key
            )
            
            self.table_info_cache[table_name] = table_info
            return table_info
    
    def list_tables(self) -> List[str]:
        """
        List all tables in the input database.
        
        Returns:
            List of table names
        """
        with sqlite3.connect(str(self.input_db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            return [row[0] for row in cursor.fetchall()]
    
    def stream_table_rows(self, 
                         table_name: str, 
                         batch_size: Optional[int] = None) -> Iterator[List[Tuple[Any, ...]]]:
        """
        Stream rows from a table in batches.
        
        Args:
            table_name: Name of the table to stream
            batch_size: Size of each batch (uses default if None)
            
        Yields:
            Batches of rows as lists of tuples
        """
        if batch_size is None:
            batch_size = self.batch_size
        
        table_info = self.get_table_info(table_name)
        
        with sqlite3.connect(str(self.input_db_path)) as conn:
            cursor = conn.cursor()
            
            # Use LIMIT and OFFSET for efficient pagination
            offset = 0
            
            while True:
                query = f"SELECT * FROM {table_name} LIMIT {batch_size} OFFSET {offset}"
                cursor.execute(query)
                batch = cursor.fetchall()
                
                if not batch:
                    break
                
                logger.debug(f"Streaming batch of {len(batch)} rows from {table_name} (offset: {offset})")
                yield batch
                
                offset += batch_size
                
                # Check if we've processed all rows
                if len(batch) < batch_size:
                    break
    
    def create_output_table(self, table_info: TableInfo) -> None:
        """
        Create a table in the output database with the same schema.
        
        Args:
            table_info: Information about the table to create
        """
        with sqlite3.connect(str(self.output_db_path)) as conn:
            cursor = conn.cursor()
            
            # Build CREATE TABLE statement
            column_definitions = []
            for col_name in table_info.columns:
                col_type = table_info.column_types[col_name]
                col_def = f"{col_name} {col_type}"
                
                if col_name == table_info.primary_key:
                    col_def += " PRIMARY KEY"
                
                column_definitions.append(col_def)
            
            create_stmt = f"CREATE TABLE IF NOT EXISTS {table_info.name} ({', '.join(column_definitions)})"
            
            logger.info(f"Creating output table: {table_info.name}")
            logger.info(f"Table {table_info.name} will have {len(table_info.columns)} columns: {table_info.columns}")
            logger.info(f"CREATE TABLE statement: {create_stmt}")
            
            cursor.execute(create_stmt)
            conn.commit()
            
            # Verify the table was created correctly
            cursor.execute(f"PRAGMA table_info({table_info.name})")
            created_columns = cursor.fetchall()
            created_column_names = [col[1] for col in created_columns]
            
            logger.info(f"Output table {table_info.name} created with columns: {created_column_names}")
            
            if len(created_column_names) != len(table_info.columns):
                logger.error(f"Column count mismatch! Expected {len(table_info.columns)}, got {len(created_column_names)}")
                logger.error(f"Expected columns: {table_info.columns}")
                logger.error(f"Created columns: {created_column_names}")
            else:
                logger.info(f"Table {table_info.name} created successfully with {len(created_column_names)} columns")
    
    def insert_batch(self, 
                    table_name: str, 
                    rows: List[Tuple[Any, ...]], 
                    table_info: TableInfo) -> None:
        """
        Insert a batch of rows into the output database.
        
        Args:
            table_name: Name of the table
            rows: List of row tuples to insert
            table_info: Information about the table
        """
        if not rows:
            return
        
        with sqlite3.connect(str(self.output_db_path)) as conn:
            cursor = conn.cursor()
            
            # Verify the output table schema before inserting
            cursor.execute(f"PRAGMA table_info({table_name})")
            output_columns = cursor.fetchall()
            output_column_count = len(output_columns)
            
            logger.debug(f"Insert batch: table {table_name} has {output_column_count} columns in output DB")
            logger.debug(f"Insert batch: expected {len(table_info.columns)} columns from table_info")
            
            if rows:
                row_value_count = len(rows[0])
                logger.debug(f"Insert batch: rows have {row_value_count} values each")
                
                if output_column_count != row_value_count:
                    logger.error(f"Column count mismatch in {table_name}!")
                    logger.error(f"Output table has {output_column_count} columns: {[col[1] for col in output_columns]}")
                    logger.error(f"Trying to insert {row_value_count} values")
                    logger.error(f"Expected columns from table_info: {table_info.columns}")
                    logger.error(f"First row values: {rows[0]}")
                    raise ValueError(f"table {table_name} has {output_column_count} columns but {row_value_count} values were supplied")
            
            # Build INSERT statement
            placeholders = ', '.join(['?' for _ in table_info.columns])
            insert_stmt = f"INSERT OR REPLACE INTO {table_name} VALUES ({placeholders})"
            
            logger.debug(f"INSERT statement: {insert_stmt}")
            
            cursor.executemany(insert_stmt, rows)
            conn.commit()
            
            logger.debug(f"Inserted {len(rows)} rows into {table_name}")
    
    def process_table(self, 
                     table_name: str, 
                     row_processor: Callable[[List[Tuple[Any, ...]], TableInfo], List[Tuple[Any, ...]]]) -> None:
        """
        Process a single table by streaming its rows and applying a processor function.
        
        Args:
            table_name: Name of the table to process
            row_processor: Function that processes batches of rows
        """
        logger.info(f"Processing table: {table_name}")
        
        table_info = self.get_table_info(table_name)
        self.create_output_table(table_info)
        
        processed_rows = 0
        
        for batch in self.stream_table_rows(table_name):
            # Process the batch
            processed_batch = row_processor(batch, table_info)
            
            # Insert processed batch into output database
            self.insert_batch(table_name, processed_batch, table_info)
            
            processed_rows += len(batch)
            self.stats.processed_rows += len(batch)
            
            if processed_rows % (self.batch_size * 10) == 0:
                logger.info(f"Processed {processed_rows:,} rows from {table_name}")
        
        logger.info(f"Completed processing table {table_name}: {processed_rows:,} rows")
        self.stats.processed_tables += 1
    
    def process_database(self, 
                        row_processor: Callable[[List[Tuple[Any, ...]], TableInfo], List[Tuple[Any, ...]]]) -> ProcessingStats:
        """
        Process the entire database by streaming all tables and applying a processor function.
        
        Args:
            row_processor: Function that processes batches of rows
            
        Returns:
            ProcessingStats object with processing statistics
        """
        logger.info(f"Starting database processing: {self.input_db_path}")
        
        self.stats.start_time = time.time()
        
        # Get list of all tables
        tables = self.list_tables()
        self.stats.total_tables = len(tables)
        
        # Calculate total rows
        total_rows = 0
        for table_name in tables:
            table_info = self.get_table_info(table_name)
            total_rows += table_info.row_count
        
        self.stats.total_rows = total_rows
        
        logger.info(f"Found {len(tables)} tables with {total_rows:,} total rows")
        
        # Process each table
        if self.enable_parallel_processing and len(tables) > 1:
            self._process_tables_parallel(tables, row_processor)
        else:
            self._process_tables_sequential(tables, row_processor)
        
        self.stats.end_time = time.time()
        
        logger.info(f"Database processing completed in {self.stats.get_elapsed_time():.2f} seconds")
        logger.info(f"Processed {self.stats.processed_rows:,} rows at {self.stats.get_rows_per_second():.2f} rows/second")
        
        return self.stats
    
    def _process_tables_sequential(self, 
                                  tables: List[str], 
                                  row_processor: Callable[[List[Tuple[Any, ...]], TableInfo], List[Tuple[Any, ...]]]) -> None:
        """Process tables sequentially."""
        for table_name in tables:
            self.process_table(table_name, row_processor)
    
    def _process_tables_parallel(self, 
                                tables: List[str], 
                                row_processor: Callable[[List[Tuple[Any, ...]], TableInfo], List[Tuple[Any, ...]]]) -> None:
        """Process tables in parallel using ThreadPoolExecutor."""
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            # Submit all table processing tasks
            future_to_table = {
                executor.submit(self.process_table, table_name, row_processor): table_name
                for table_name in tables
            }
            
            # Process completed tasks
            for future in as_completed(future_to_table):
                table_name = future_to_table[future]
                try:
                    future.result()  # This will raise any exception that occurred
                    logger.info(f"Successfully processed table: {table_name}")
                except Exception as e:
                    logger.error(f"Error processing table {table_name}: {e}")
                    raise
    
    def copy_database_schema(self) -> None:
        """
        Copy the database schema (without data) from input to output database.
        This is useful for preparing the output database structure.
        """
        logger.info("Copying database schema")
        
        with sqlite3.connect(str(self.input_db_path)) as input_conn:
            with sqlite3.connect(str(self.output_db_path)) as output_conn:
                # Get all CREATE statements
                cursor = input_conn.cursor()
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
                
                for row in cursor.fetchall():
                    if row[0]:  # Skip None values
                        output_conn.execute(row[0])
                
                output_conn.commit()
        
        logger.info("Database schema copied successfully")
    
    def validate_output_database(self) -> bool:
        """
        Validate that the output database has the same structure as input.
        
        Returns:
            True if validation passes, False otherwise
        """
        logger.info("Validating output database structure")
        
        try:
            input_tables = self.list_tables()
            
            with sqlite3.connect(str(self.output_db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                output_tables = [row[0] for row in cursor.fetchall()]
            
            # Check if all input tables exist in output
            missing_tables = set(input_tables) - set(output_tables)
            if missing_tables:
                logger.error(f"Missing tables in output database: {missing_tables}")
                return False
            
            # Check table schemas
            for table_name in input_tables:
                input_info = self.get_table_info(table_name)
                
                with sqlite3.connect(str(self.output_db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    output_columns = [col[1] for col in cursor.fetchall()]
                
                if input_info.columns != output_columns:
                    logger.error(f"Column mismatch in table {table_name}")
                    return False
            
            logger.info("Output database validation successful")
            return True
        
        except Exception as e:
            logger.error(f"Error validating output database: {e}")
            return False
    
    def get_processing_progress(self) -> Dict[str, Any]:
        """
        Get current processing progress.
        
        Returns:
            Dictionary with progress information
        """
        return {
            "total_tables": self.stats.total_tables,
            "processed_tables": self.stats.processed_tables,
            "total_rows": self.stats.total_rows,
            "processed_rows": self.stats.processed_rows,
            "anonymized_rows": self.stats.anonymized_rows,
            "elapsed_time": self.stats.get_elapsed_time(),
            "rows_per_second": self.stats.get_rows_per_second(),
            "progress_percent": (self.stats.processed_rows / self.stats.total_rows * 100) if self.stats.total_rows > 0 else 0
        }