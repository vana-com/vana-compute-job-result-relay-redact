"""
PII Anonymization Pipeline for streaming processing of query results.

This module integrates Microsoft Presidio with the SQLite stream processor to
provide memory-efficient PII anonymization for large datasets. It supports:
- Streaming PII detection and anonymization
- Configurable PII entity types and anonymization strategies
- Batch processing for optimal performance
- Column-level PII detection configuration
- Detailed anonymization statistics and logging
"""

import logging
import time
import json
from typing import Dict, List, Tuple, Any, Optional, Set
from dataclasses import dataclass
from pathlib import Path
import sqlite3

from presidio_config import PresidioConfig, PresidioManager
from sqlite_stream_processor import SQLiteStreamProcessor, TableInfo, ProcessingStats


logger = logging.getLogger(__name__)


@dataclass
class ColumnConfig:
    """Configuration for PII detection on a specific column."""
    column_name: str
    enabled: bool = True
    entity_types: Optional[List[str]] = None  # None means all enabled entities
    language: str = "en"
    confidence_threshold: Optional[float] = None  # None means use entity default


@dataclass
class TableConfig:
    """Configuration for PII detection on a specific table."""
    table_name: str
    enabled: bool = True
    columns: Dict[str, ColumnConfig] = None
    
    def __post_init__(self):
        if self.columns is None:
            self.columns = {}


@dataclass
class AnonymizationStats:
    """Statistics for the anonymization process."""
    total_values_processed: int = 0
    total_values_anonymized: int = 0
    entities_found: Dict[str, int] = None
    tables_processed: Dict[str, int] = None
    columns_processed: Dict[str, int] = None
    processing_time: float = 0
    
    def __post_init__(self):
        if self.entities_found is None:
            self.entities_found = {}
        if self.tables_processed is None:
            self.tables_processed = {}
        if self.columns_processed is None:
            self.columns_processed = {}


class PIIAnonymizationPipeline:
    """
    Pipeline for anonymizing PII in SQLite databases using streaming processing.
    
    This class combines the SQLite stream processor with Presidio PII detection
    and anonymization to provide memory-efficient processing of large datasets.
    """
    
    def __init__(self, 
                 presidio_config: PresidioConfig,
                 input_db_path: Path,
                 output_db_path: Path,
                 table_configs: Optional[Dict[str, TableConfig]] = None):
        """
        Initialize the PII anonymization pipeline.
        
        Args:
            presidio_config: Configuration for Presidio PII detection
            input_db_path: Path to input SQLite database
            output_db_path: Path to output SQLite database
            table_configs: Optional table-specific configurations
        """
        self.presidio_config = presidio_config
        self.input_db_path = Path(input_db_path)
        self.output_db_path = Path(output_db_path)
        self.table_configs = table_configs or {}
        
        # Initialize Presidio manager
        self.presidio_manager = PresidioManager(presidio_config)
        
        # Initialize SQLite stream processor
        self.stream_processor = SQLiteStreamProcessor(
            input_db_path=input_db_path,
            output_db_path=output_db_path,
            batch_size=presidio_config.batch_processing.batch_size,
            max_memory_mb=presidio_config.batch_processing.max_memory_mb,
            enable_parallel_processing=presidio_config.batch_processing.enable_parallel_processing,
            num_workers=presidio_config.batch_processing.num_workers
        )
        
        # Initialize statistics
        self.anonymization_stats = AnonymizationStats()
        
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        log_level = getattr(logging, self.presidio_config.log_level.upper())
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        if self.presidio_config.debug_mode:
            logger.setLevel(logging.DEBUG)
    
    def _get_column_config(self, table_name: str, column_name: str) -> ColumnConfig:
        """
        Get configuration for a specific column.
        
        Args:
            table_name: Name of the table
            column_name: Name of the column
            
        Returns:
            ColumnConfig object
        """
        if table_name in self.table_configs:
            table_config = self.table_configs[table_name]
            if column_name in table_config.columns:
                return table_config.columns[column_name]
        
        # Return default configuration
        return ColumnConfig(column_name=column_name)
    
    def _should_process_column(self, table_name: str, column_name: str, column_type: str) -> bool:
        """
        Determine if a column should be processed for PII.
        
        Args:
            table_name: Name of the table
            column_name: Name of the column
            column_type: SQLite column type
            
        Returns:
            True if the column should be processed, False otherwise
        """
        # Process text columns and numeric columns that might contain PII
        # Include numeric types as they can contain SSNs, phone numbers, credit cards, dates, etc.
        processable_types = [
            'TEXT', 'VARCHAR', 'CHAR', 'STRING',  # Text types
            'INTEGER', 'INT', 'NUMERIC', 'REAL', 'FLOAT', 'DOUBLE', 'NUM',  # Numeric types
            'DATE', 'DATETIME', 'TIMESTAMP'  # Date/time types
        ]
        
        if column_type.upper() not in processable_types:
            return False
        
        # Exclude common ID columns that shouldn't be treated as PII
        id_column_patterns = ['user_id', 'id', 'uuid', 'guid', 'key', 'pk']
        if column_name.lower() in id_column_patterns or column_name.lower().endswith('_id'):
            return False
        
        # Check table configuration
        if table_name in self.table_configs:
            table_config = self.table_configs[table_name]
            if not table_config.enabled:
                return False
            
            if column_name in table_config.columns:
                return table_config.columns[column_name].enabled
        
        # Default: process all processable columns
        return True
    
    def _anonymize_value(self, 
                        value: Any, 
                        table_name: str, 
                        column_name: str) -> Tuple[Any, bool]:
        """
        Anonymize a single value if it contains PII.
        
        Args:
            value: The value to check and potentially anonymize
            table_name: Name of the table
            column_name: Name of the column
            
        Returns:
            Tuple of (anonymized_value, was_anonymized)
        """
        # Skip None values
        if value is None:
            return value, False
        
        # Convert to string for processing
        text_value = str(value)
        
        # Skip empty or very short values
        if not text_value or len(text_value.strip()) < 2:
            return value, False
        
        # Get column configuration
        column_config = self._get_column_config(table_name, column_name)
        
        # Check if column processing is enabled
        if not column_config.enabled:
            return value, False
        
        # Analyze text for PII
        try:
            analyzer_results = self.presidio_manager.analyze_text(
                text_value, 
                language=column_config.language
            )
            
            # Filter results based on column configuration
            if column_config.entity_types:
                analyzer_results = [
                    result for result in analyzer_results 
                    if result.entity_type in column_config.entity_types
                ]
            
            # Apply confidence threshold
            if column_config.confidence_threshold:
                analyzer_results = [
                    result for result in analyzer_results
                    if result.score >= column_config.confidence_threshold
                ]
            
            # If no PII found, return original value
            if not analyzer_results:
                return value, False
            
            # Anonymize the text
            anonymized_text = self.presidio_manager.anonymize_text(
                text_value, 
                analyzer_results
            )
            
            # Update statistics
            for result in analyzer_results:
                entity_type = result.entity_type
                self.anonymization_stats.entities_found[entity_type] = \
                    self.anonymization_stats.entities_found.get(entity_type, 0) + 1
                        
            return anonymized_text, True
            
        except Exception as e:
            logger.error(f"Error anonymizing value in {table_name}.{column_name}: {e}")
            return value, False
    
    def _process_row_batch(self, 
                          rows: List[Tuple[Any, ...]], 
                          table_info: TableInfo) -> List[Tuple[Any, ...]]:
        """
        Process a batch of rows for PII anonymization.
        
        Args:
            rows: List of row tuples to process
            table_info: Information about the table
            
        Returns:
            List of processed row tuples
        """
        if not self.presidio_manager.is_enabled():
            logger.debug("PII anonymization is disabled, returning rows unchanged")
            return rows
        
        processed_rows = []
        
        for row in rows:
            processed_row = []
            row_was_anonymized = False
            
            for i, value in enumerate(row):
                column_name = table_info.columns[i]
                column_type = table_info.column_types[column_name]
                
                # Check if this column should be processed
                if self._should_process_column(table_info.name, column_name, column_type):
                    anonymized_value, was_anonymized = self._anonymize_value(
                        value, 
                        table_info.name, 
                        column_name
                    )
                    processed_row.append(anonymized_value)
                    
                    if was_anonymized:
                        row_was_anonymized = True
                        self.anonymization_stats.total_values_anonymized += 1
                    
                    self.anonymization_stats.total_values_processed += 1
                else:
                    processed_row.append(value)
            
            processed_rows.append(tuple(processed_row))
            
            # Update table and column statistics
            table_name = table_info.name
            self.anonymization_stats.tables_processed[table_name] = \
                self.anonymization_stats.tables_processed.get(table_name, 0) + 1
            
            if row_was_anonymized:
                self.stream_processor.stats.anonymized_rows += 1
        
        return processed_rows
    
    def process_database(self) -> Tuple[ProcessingStats, AnonymizationStats]:
        """
        Process the entire database for PII anonymization.
        
        Returns:
            Tuple of (ProcessingStats, AnonymizationStats)
        """
        logger.info("Starting PII anonymization pipeline")
        
        if not self.presidio_manager.is_enabled():
            logger.warning("PII anonymization is disabled in configuration")
            # Still process the database but without anonymization
            processing_stats = self.stream_processor.process_database(
                lambda rows, table_info: rows
            )
            return processing_stats, self.anonymization_stats
        
        start_time = time.time()
        
        # Process the database using the stream processor
        processing_stats = self.stream_processor.process_database(
            self._process_row_batch
        )
        
        # Update anonymization statistics
        self.anonymization_stats.processing_time = time.time() - start_time
        
        logger.info(f"PII anonymization completed in {self.anonymization_stats.processing_time:.2f} seconds")
        logger.info(f"Processed {self.anonymization_stats.total_values_processed:,} values")
        logger.info(f"Anonymized {self.anonymization_stats.total_values_anonymized:,} values")
        
        # Log entity statistics
        if self.anonymization_stats.entities_found:
            logger.info("PII entities found:")
            for entity_type, count in self.anonymization_stats.entities_found.items():
                logger.info(f"  {entity_type}: {count}")
        
        return processing_stats, self.anonymization_stats
    
    def validate_configuration(self) -> bool:
        """
        Validate the pipeline configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check if input database exists
            if not self.input_db_path.exists():
                logger.error(f"Input database not found: {self.input_db_path}")
                return False
            
            # Check if Presidio is properly configured
            if not self.presidio_manager.is_enabled():
                logger.warning("Presidio is disabled in configuration")
                return True
            
            # Validate table configurations
            actual_tables = self.stream_processor.list_tables()
            for table_name in self.table_configs.keys():
                if table_name not in actual_tables:
                    logger.error(f"Configured table '{table_name}' not found in database")
                    return False
            
            # Validate column configurations
            for table_name, table_config in self.table_configs.items():
                table_info = self.stream_processor.get_table_info(table_name)
                for column_name in table_config.columns.keys():
                    if column_name not in table_info.columns:
                        logger.error(f"Configured column '{column_name}' not found in table '{table_name}'")
                        return False
            
            logger.info("Pipeline configuration validation successful")
            return True
            
        except Exception as e:
            logger.error(f"Error validating configuration: {e}")
            return False
    
    def get_anonymization_report(self) -> Dict[str, Any]:
        """
        Get a comprehensive report of the anonymization process.
        
        Returns:
            Dictionary containing detailed anonymization statistics
        """
        processing_progress = self.stream_processor.get_processing_progress()
        
        return {
            "pipeline_config": {
                "enabled": self.presidio_config.enabled,
                "batch_size": self.presidio_config.batch_processing.batch_size,
                "parallel_processing": self.presidio_config.batch_processing.enable_parallel_processing,
                "num_workers": self.presidio_config.batch_processing.num_workers
            },
            "processing_stats": processing_progress,
            "anonymization_stats": {
                "total_values_processed": self.anonymization_stats.total_values_processed,
                "total_values_anonymized": self.anonymization_stats.total_values_anonymized,
                "anonymization_rate": (
                    self.anonymization_stats.total_values_anonymized / 
                    self.anonymization_stats.total_values_processed * 100
                ) if self.anonymization_stats.total_values_processed > 0 else 0,
                "entities_found": self.anonymization_stats.entities_found,
                "tables_processed": self.anonymization_stats.tables_processed,
                "processing_time": self.anonymization_stats.processing_time
            },
            "presidio_config": {
                "enabled_entities": self.presidio_config.get_enabled_entities(),
                "nlp_model": self.presidio_config.nlp.model_name,
                "supported_languages": self.presidio_config.nlp.supported_languages
            }
        }
    
    def save_anonymization_report(self, report_path: Path) -> None:
        """
        Save the anonymization report to a JSON file.
        
        Args:
            report_path: Path to save the report
        """
        report = self.get_anonymization_report()
        
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Anonymization report saved to: {report_path}")


def create_pipeline_from_config(config_path: Path, 
                               input_db_path: Path, 
                               output_db_path: Path,
                               table_configs: Optional[Dict[str, TableConfig]] = None) -> PIIAnonymizationPipeline:
    """
    Create a PII anonymization pipeline from a configuration file.
    
    Args:
        config_path: Path to the Presidio configuration file
        input_db_path: Path to input SQLite database
        output_db_path: Path to output SQLite database
        table_configs: Optional table-specific configurations
        
    Returns:
        PIIAnonymizationPipeline instance
    """
    presidio_config = PresidioConfig.from_file(config_path)
    
    return PIIAnonymizationPipeline(
        presidio_config=presidio_config,
        input_db_path=input_db_path,
        output_db_path=output_db_path,
        table_configs=table_configs
    )


def create_default_pipeline(input_db_path: Path, 
                           output_db_path: Path) -> PIIAnonymizationPipeline:
    """
    Create a PII anonymization pipeline with default configuration.
    
    Args:
        input_db_path: Path to input SQLite database
        output_db_path: Path to output SQLite database
        
    Returns:
        PIIAnonymizationPipeline instance
    """
    presidio_config = PresidioConfig.default()
    
    return PIIAnonymizationPipeline(
        presidio_config=presidio_config,
        input_db_path=input_db_path,
        output_db_path=output_db_path
    )