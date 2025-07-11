"""
Configuration system for Presidio PII detection and anonymization.

This module provides a configurable system for PII detection and anonymization
using Microsoft Presidio. It supports:
- Configurable PII entity types and detection settings
- Custom anonymization strategies per entity type
- Multiple anonymization operations (replace, mask, redact, encrypt, etc.)
- NLP model configuration
- Batch processing settings for large datasets
"""

print("DEBUG: presidio_config.py module loaded")

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from presidio_anonymizer.operators import Operator
import re

logger = logging.getLogger(__name__)


# Custom masking functions for use with Presidio lambda operators
def mask_email(email: str) -> str:
    """Mask email in format ka***@***.com"""
    if '@' not in email:
        return email
        
    username, domain = email.split('@', 1)
    
    # Show first 2 chars of username, mask rest
    if len(username) <= 2:
        masked_username = username
    else:
        masked_username = username[:2] + '*' * (len(username) - 2)
    
    # Show first and last part of domain, mask middle
    if '.' in domain:
        domain_parts = domain.split('.')
        if len(domain_parts) >= 2:
            main_domain = domain_parts[0]
            tld = domain_parts[-1]
            
            if len(main_domain) <= 2:
                masked_domain = main_domain
            else:
                masked_domain = main_domain[:1] + '*' * (len(main_domain) - 1)
            
            masked_domain = masked_domain + '.' + tld
        else:
            masked_domain = domain
    else:
        masked_domain = domain
        
    return f"{masked_username}@{masked_domain}"


def mask_person(name: str) -> str:
    """Mask person name in format Jo*** Do****"""
    parts = name.split()
    masked_parts = []
    
    for part in parts:
        if len(part) <= 2:
            masked_parts.append(part)
        else:
            masked_parts.append(part[:2] + '*' * (len(part) - 2))
    
    return ' '.join(masked_parts)


def mask_location(location: str) -> str:
    """Mask location in format 1** P*** rd"""
    # Handle full addresses by applying location masking to the entire string
    # regardless of what specific parts were detected by spaCy
    
    # Split by common delimiters but preserve the structure
    import re
    
    # Split by comma first to handle "street, city, country" format
    comma_parts = location.split(',')
    masked_comma_parts = []
    
    for comma_part in comma_parts:
        comma_part = comma_part.strip()
        if not comma_part:
            continue
            
        # Split each comma part by spaces
        parts = re.split(r'\s+', comma_part)
        masked_parts = []
        
        for part in parts:
            if not part:
                continue
            
            # Check if it's likely a number
            if part.isdigit():
                if len(part) <= 1:
                    masked_parts.append(part)
                else:
                    masked_parts.append(part[:1] + '*' * (len(part) - 1))
            # Check if it's a short word that should be preserved (like "St", "Ave", etc.)
            elif len(part) <= 2 or part.lower() in ['st', 'ave', 'rd', 'dr', 'ln', 'blvd', 'way', 'ct', 'pl']:
                masked_parts.append(part)
            else:
                # Mask longer words (street names, city names, country names)
                masked_parts.append(part[:1] + '*' * (len(part) - 1))
        
        masked_comma_parts.append(' '.join(masked_parts))
    
    return ', '.join(masked_comma_parts)


@dataclass
class EntityConfig:
    """Configuration for a specific PII entity type."""
    entity_type: str
    enabled: bool = True
    confidence_threshold: float = 0.5
    context_words: List[str] = field(default_factory=list)
    deny_list: List[str] = field(default_factory=list)
    regex_patterns: List[str] = field(default_factory=list)
    anonymization_strategy: str = "replace"
    anonymization_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnonymizationConfig:
    """Configuration for anonymization operations."""
    default_strategy: str = "replace"
    default_replacement: str = "<REDACTED>"
    preserve_format: bool = True
    
    # Strategy-specific configurations
    mask_char: str = "*"
    mask_from_end: bool = True
    hash_type: str = "sha256"
    encryption_key: Optional[str] = None


@dataclass
class BatchProcessingConfig:
    """Configuration for batch processing large datasets."""
    batch_size: int = 1000
    max_memory_mb: int = 512
    enable_parallel_processing: bool = True
    num_workers: int = 4


@dataclass
class NlpConfig:
    """Configuration for NLP engine."""
    engine_name: str = "spacy"
    model_name: str = "en_core_web_sm"
    supported_languages: List[str] = field(default_factory=lambda: ["en"])
    custom_models: Dict[str, str] = field(default_factory=dict)


@dataclass
class PresidioConfig:
    """Main configuration for Presidio PII detection and anonymization."""
    
    # Entity configurations
    entities: Dict[str, EntityConfig] = field(default_factory=dict)
    
    # Anonymization settings
    anonymization: AnonymizationConfig = field(default_factory=AnonymizationConfig)
    
    # Batch processing settings
    batch_processing: BatchProcessingConfig = field(default_factory=BatchProcessingConfig)
    
    # NLP engine configuration
    nlp: NlpConfig = field(default_factory=NlpConfig)
    
    # Global settings
    enabled: bool = True
    debug_mode: bool = False
    log_level: str = "INFO"
    
    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> 'PresidioConfig':
        """Load configuration from a JSON file."""
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        return cls.from_dict(config_data)
    
    @classmethod
    def from_dict(cls, config_data: Dict[str, Any]) -> 'PresidioConfig':
        """Create configuration from a dictionary."""
        # Parse entity configurations
        entities = {}
        for entity_name, entity_data in config_data.get("entities", {}).items():
            entities[entity_name] = EntityConfig(
                entity_type=entity_data["entity_type"],
                enabled=entity_data.get("enabled", True),
                confidence_threshold=entity_data.get("confidence_threshold", 0.5),
                context_words=entity_data.get("context_words", []),
                deny_list=entity_data.get("deny_list", []),
                regex_patterns=entity_data.get("regex_patterns", []),
                anonymization_strategy=entity_data.get("anonymization_strategy", "replace"),
                anonymization_params=entity_data.get("anonymization_params", {})
            )
        
        # Parse anonymization configuration
        anon_data = config_data.get("anonymization", {})
        anonymization = AnonymizationConfig(
            default_strategy=anon_data.get("default_strategy", "replace"),
            default_replacement=anon_data.get("default_replacement", "<REDACTED>"),
            preserve_format=anon_data.get("preserve_format", True),
            mask_char=anon_data.get("mask_char", "*"),
            mask_from_end=anon_data.get("mask_from_end", True),
            hash_type=anon_data.get("hash_type", "sha256"),
            encryption_key=anon_data.get("encryption_key")
        )
        
        # Parse batch processing configuration
        batch_data = config_data.get("batch_processing", {})
        batch_processing = BatchProcessingConfig(
            batch_size=batch_data.get("batch_size", 1000),
            max_memory_mb=batch_data.get("max_memory_mb", 512),
            enable_parallel_processing=batch_data.get("enable_parallel_processing", True),
            num_workers=batch_data.get("num_workers", 4)
        )
        
        # Parse NLP configuration
        nlp_data = config_data.get("nlp", {})
        nlp = NlpConfig(
            engine_name=nlp_data.get("engine_name", "spacy"),
            model_name=nlp_data.get("model_name", "en_core_web_sm"),
            supported_languages=nlp_data.get("supported_languages", ["en"]),
            custom_models=nlp_data.get("custom_models", {})
        )
        
        return cls(
            entities=entities,
            anonymization=anonymization,
            batch_processing=batch_processing,
            nlp=nlp,
            enabled=config_data.get("enabled", True),
            debug_mode=config_data.get("debug_mode", False),
            log_level=config_data.get("log_level", "INFO")
        )
    
    @classmethod
    def default(cls) -> 'PresidioConfig':
        """Create a default configuration by loading from the default JSON config file."""
        default_config_path = Path(__file__).parent.parent / "config" / "presidio_config.json"
        
        if default_config_path.exists():
            return cls.from_file(default_config_path)
        else:
            # Fallback to minimal config if JSON file doesn't exist
            return cls()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        entities_dict = {}
        for name, entity in self.entities.items():
            entities_dict[name] = {
                "entity_type": entity.entity_type,
                "enabled": entity.enabled,
                "confidence_threshold": entity.confidence_threshold,
                "context_words": entity.context_words,
                "deny_list": entity.deny_list,
                "regex_patterns": entity.regex_patterns,
                "anonymization_strategy": entity.anonymization_strategy,
                "anonymization_params": entity.anonymization_params
            }
        
        return {
            "entities": entities_dict,
            "anonymization": {
                "default_strategy": self.anonymization.default_strategy,
                "default_replacement": self.anonymization.default_replacement,
                "preserve_format": self.anonymization.preserve_format,
                "mask_char": self.anonymization.mask_char,
                "mask_from_end": self.anonymization.mask_from_end,
                "hash_type": self.anonymization.hash_type,
                "encryption_key": self.anonymization.encryption_key
            },
            "batch_processing": {
                "batch_size": self.batch_processing.batch_size,
                "max_memory_mb": self.batch_processing.max_memory_mb,
                "enable_parallel_processing": self.batch_processing.enable_parallel_processing,
                "num_workers": self.batch_processing.num_workers
            },
            "nlp": {
                "engine_name": self.nlp.engine_name,
                "model_name": self.nlp.model_name,
                "supported_languages": self.nlp.supported_languages,
                "custom_models": self.nlp.custom_models
            },
            "enabled": self.enabled,
            "debug_mode": self.debug_mode,
            "log_level": self.log_level
        }
    
    def save_to_file(self, config_path: Union[str, Path]) -> None:
        """Save configuration to a JSON file."""
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def get_enabled_entities(self) -> List[str]:
        """Get list of enabled entity types."""
        return [entity.entity_type for entity in self.entities.values() if entity.enabled]
    
    def get_anonymization_operators(self) -> Dict[str, OperatorConfig]:
        """Get anonymization operators for enabled entities."""
        operators = {}
        
        for entity_config in self.entities.values():
            if not entity_config.enabled:
                continue
                
            strategy = entity_config.anonymization_strategy
            params = entity_config.anonymization_params.copy()
            
            # Apply default parameters based on strategy
            if strategy == "replace" and "new_value" not in params:
                params["new_value"] = f"<{entity_config.entity_type}>"
            elif strategy == "mask":
                params.setdefault("masking_char", self.anonymization.mask_char)
                params.setdefault("from_end", self.anonymization.mask_from_end)
            elif strategy == "hash":
                params.setdefault("hash_type", self.anonymization.hash_type)
            elif strategy == "encrypt" and self.anonymization.encryption_key:
                params.setdefault("key", self.anonymization.encryption_key)
            elif strategy == "custom" and "lambda" in params:
                # Handle custom lambda functions
                lambda_func_name = params["lambda"]
                if lambda_func_name == "mask_email":
                    params["lambda"] = mask_email
                elif lambda_func_name == "mask_person":
                    params["lambda"] = mask_person
                elif lambda_func_name == "mask_location":
                    params["lambda"] = mask_location
            
            operators[entity_config.entity_type] = OperatorConfig(strategy, params)
        
        # Add default operator for any unspecified entities
        operators["DEFAULT"] = OperatorConfig(
            self.anonymization.default_strategy,
            {"new_value": self.anonymization.default_replacement}
        )
        
        return operators


class PresidioManager:
    """Manager class for Presidio analyzer and anonymizer engines."""
    
    def __init__(self, config: PresidioConfig):
        print("DEBUG: PresidioManager.__init__ called")
        self.config = config
        self.analyzer = None
        self.anonymizer = None
        self._initialize_engines()
    
    def _initialize_engines(self) -> None:
        """Initialize Presidio analyzer and anonymizer engines."""
        print("DEBUG: _initialize_engines called")
        if not self.config.enabled:
            print("DEBUG: config not enabled, returning")
            return
        
        # Initialize NLP engine
        nlp_config = {
            "nlp_engine_name": self.config.nlp.engine_name,
            "models": [
                {
                    "lang_code": lang,
                    "model_name": self.config.nlp.custom_models.get(lang, self.config.nlp.model_name)
                }
                for lang in self.config.nlp.supported_languages
            ]
        }
        
        provider = NlpEngineProvider(nlp_configuration=nlp_config)
        nlp_engine = provider.create_engine()
        
        # Initialize analyzer
        self.analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine,
            supported_languages=self.config.nlp.supported_languages
        )
        
        # Add custom recognizers
        self._add_custom_recognizers()
        
        # Initialize anonymizer
        self.anonymizer = AnonymizerEngine()
    
    def _add_custom_recognizers(self) -> None:
        """Add custom recognizers based on configuration."""
        print("DEBUG: _add_custom_recognizers called")
        try:
            for entity_config in self.config.entities.values():
                if not entity_config.enabled:
                    continue
                    
                # Create custom recognizer if deny_list or regex_patterns are provided
                if entity_config.deny_list or entity_config.regex_patterns:
                    # Convert regex patterns to proper format
                    patterns = []
                    if entity_config.regex_patterns:
                        for pattern in entity_config.regex_patterns:
                            try:
                                if isinstance(pattern, dict):
                                    patterns.append(Pattern(
                                        name=pattern["name"],
                                        regex=pattern["regex"],
                                        score=pattern.get("score", 0.8)
                                    ))
                                else:
                                    patterns.append(pattern)
                            except Exception as e:
                                logger.warning(f"Failed to create pattern {pattern}: {e}")
                                continue
                    
                    try:
                        logger.info(f"Creating custom recognizer for {entity_config.entity_type} with {len(patterns)} patterns")
                        recognizer = PatternRecognizer(
                            supported_entity=entity_config.entity_type,
                            deny_list=entity_config.deny_list if entity_config.deny_list else None,
                            patterns=patterns if patterns else None,
                            context=entity_config.context_words if entity_config.context_words else None
                        )
                        self.analyzer.registry.add_recognizer(recognizer)
                        logger.info(f"Successfully added custom recognizer for {entity_config.entity_type} with {len(patterns)} patterns")
                    except Exception as e:
                        logger.warning(f"Failed to add custom recognizer for {entity_config.entity_type}: {e}")
                        
        except Exception as e:
            logger.error(f"Error in _add_custom_recognizers: {e}")
            # Continue without custom recognizers rather than failing
        
        # Add custom address recognizer to catch complete addresses        
        try:
            address_patterns = [
                Pattern(
                    name="full_address",
                    regex=r"\b\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:St|Ave|Rd|Dr|Ln|Blvd|Way|Ct|Pl|Street|Avenue|Road|Drive|Lane|Boulevard)\b(?:,\s*[A-Za-z\s]+)*",
                    score=0.8
                ),
                Pattern(
                    name="street_address",
                    regex=r"\b\d+\s+[A-Za-z\s]+(?:St|Ave|Rd|Dr|Ln|Blvd|Way|Ct|Pl|Street|Avenue|Road|Drive|Lane|Boulevard)\b",
                    score=0.7
                ),
                Pattern(
                    name="address_with_city",
                    regex=r"\b\d+\s+[A-Za-z\s]+,\s*[A-Za-z\s]+,\s*[A-Za-z\s]+",
                    score=0.8
                )
            ]
            
            address_recognizer = PatternRecognizer(
                supported_entity="LOCATION",
                patterns=address_patterns,
                context=["address", "location", "street", "avenue", "road"]
            )
            self.analyzer.registry.add_recognizer(address_recognizer)
            logger.debug("Added custom address recognizer")
        except Exception as e:
            logger.warning(f"Failed to add custom address recognizer: {e}")
    
    
    def analyze_text(self, text: str, language: str = "en") -> List[Any]:
        """Analyze text for PII entities."""
        if not self.config.enabled or not self.analyzer:
            return []
        
        enabled_entities = self.config.get_enabled_entities()
        return self.analyzer.analyze(
            text=text,
            language=language,
            entities=enabled_entities if enabled_entities else None
        )
    
    def anonymize_text(self, text: str, analyzer_results: List[Any]) -> str:
        """Anonymize text based on analyzer results."""
        if not self.config.enabled or not self.anonymizer:
            return text
        
        operators = self.config.get_anonymization_operators()
        result = self.anonymizer.anonymize(
            text=text,
            analyzer_results=analyzer_results,
            operators=operators
        )
        return result.text
    
    def process_text(self, text: str, language: str = "en") -> str:
        """Process text: analyze and anonymize in one call."""
        analyzer_results = self.analyze_text(text, language)
        return self.anonymize_text(text, analyzer_results)
    
    def is_enabled(self) -> bool:
        """Check if PII processing is enabled."""
        return self.config.enabled and self.analyzer is not None and self.anonymizer is not None