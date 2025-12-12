"""
Multi-tenant LightRAG instance manager.
Manages a pool of LightRAG instances, one per (tenant_id, project_id) combination.
Fetches LLM configurations from database instead of environment variables.
"""

import asyncio
from typing import Dict, Tuple, Optional, Any
from datetime import datetime, timedelta
from collections import OrderedDict
from lightrag import LightRAG
from lightrag.utils import logger


class LightRAGInstanceManager:
    """
    Manages multiple LightRAG instances for multi-tenant support.
    
    Each (tenant_id, project_id) combination gets its own LightRAG instance.
    Implements LRU cache to limit memory usage.
    LLM configurations are fetched from database per project.
    """
    
    def __init__(
        self,
        base_config: dict,
        llm_config_service=None,
        max_instances: int = 100,
        ttl_minutes: int = 60
    ):
        """
        Initialize the instance manager.
        
        Args:
            base_config: Base configuration dict for LightRAG (without LLM configs)
            llm_config_service: LLMConfigService instance for fetching LLM configurations
            max_instances: Maximum number of cached instances (LRU eviction)
            ttl_minutes: Time-to-live for inactive instances in minutes
        """
        self.base_config = base_config
        self.llm_config_service = llm_config_service
        self.max_instances = max_instances
        self.ttl = timedelta(minutes=ttl_minutes)
        
        # LRU cache: (tenant_id, project_id) -> LightRAG instance
        self._instances: OrderedDict[Tuple[str, str], LightRAG] = OrderedDict()
        
        # Last access time for each instance
        self._last_access: Dict[Tuple[str, str], datetime] = {}
        
        # Lock for thread-safe access
        self._lock = asyncio.Lock()
        
        logger.info(
            f"LightRAG Instance Manager initialized: max_instances={max_instances}, ttl={ttl_minutes}min"
        )
        
        if llm_config_service:
            logger.info("LLM configurations will be fetched from database")
        else:
            logger.warning("No LLMConfigService provided - will use base_config LLM settings")
    
    async def get_instance(self, tenant_id: str, project_id: str) -> LightRAG:
        """
        Get or create a LightRAG instance for the given tenant and project.
        
        Fetches LLM configuration from database if llm_config_service is available.
        
        Args:
            tenant_id: Tenant identifier
            project_id: Project identifier
            
        Returns:
            LightRAG instance configured for this tenant/project
            
        Raises:
            ValueError: If no LLM configuration found for project
        """
        async with self._lock:
            key = (tenant_id, project_id)
            
            # Check if instance exists and is not expired
            if key in self._instances:
                last_access = self._last_access.get(key)
                if last_access and (datetime.now() - last_access) > self.ttl:
                    # Instance expired, remove it
                    logger.info(f"Removing expired instance for tenant={tenant_id}, project={project_id}")
                    await self._remove_instance(key)
                else:
                    # Move to end (most recently used)
                    self._instances.move_to_end(key)
                    self._last_access[key] = datetime.now()
                    logger.debug(f"Reusing instance for tenant={tenant_id}, project={project_id}")
                    return self._instances[key]
            
            # Fetch LLM configuration from database
            llm_config = None
            if self.llm_config_service:
                try:
                    llm_config = await self.llm_config_service.get_default_config(project_id)
                    if not llm_config:
                        raise ValueError(
                            f"No default LLM configuration found for project {project_id}. "
                            "Please create an LLM configuration via /llm-configs endpoint."
                        )
                    logger.info(
                        f"Using LLM config from database: provider={llm_config['provider']}, "
                        f"model={llm_config['model_name']}"
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch LLM config for project {project_id}: {e}")
                    raise ValueError(f"Failed to fetch LLM configuration: {e}")
            
            # Create LLM and embedding functions from config
            instance_config = self.base_config.copy()
            
            if llm_config:
                # Import factory functions
                from lightrag.api.llm_factory import create_llm_from_config, create_embedding_from_config
                
                # Create LLM function from database config
                instance_config["llm_model_func"] = create_llm_from_config(llm_config)
                
                # Create embedding function if specified
                embedding_func = create_embedding_from_config(llm_config)
                if embedding_func:
                    instance_config["embedding_func"] = embedding_func
                    logger.info(f"Using custom embedding model: {llm_config.get('embedding_model')}")
            
            # Create new instance
            logger.info(f"Creating new LightRAG instance for tenant={tenant_id}, project={project_id}")
            instance = LightRAG(
                **instance_config,
                tenant_id=tenant_id,
                project_id=project_id,
            )
            
            # Add to cache
            self._instances[key] = instance
            self._last_access[key] = datetime.now()
            
            # Enforce max instances limit (LRU eviction)
            if len(self._instances) > self.max_instances:
                # Remove least recently used
                oldest_key = next(iter(self._instances))
                logger.info(
                    f"Cache full, evicting LRU instance: tenant={oldest_key[0]}, project={oldest_key[1]}"
                )
                await self._remove_instance(oldest_key)
            
            logger.info(
                f"Active instances: {len(self._instances)}/{self.max_instances} "
                f"[tenant={tenant_id}, project={project_id}]"
            )
            
            return instance
    
    async def _remove_instance(self, key: Tuple[str, str]):
        """Remove an instance and clean up resources."""
        if key in self._instances:
            instance = self._instances[key]
            
            # Cleanup storage connections if needed
            try:
                # Finalize all storages
                if hasattr(instance, 'llm_response_cache'):
                    await instance.llm_response_cache.finalize()
                if hasattr(instance, 'text_chunks'):
                    await instance.text_chunks.finalize()
                if hasattr(instance, 'full_docs'):
                    await instance.full_docs.finalize()
                if hasattr(instance, 'entities_vdb'):
                    await instance.entities_vdb.finalize()
                if hasattr(instance, 'relationships_vdb'):
                    await instance.relationships_vdb.finalize()
                if hasattr(instance, 'chunks_vdb'):
                    await instance.chunks_vdb.finalize()
                if hasattr(instance, 'chunk_entity_relation_graph'):
                    await instance.chunk_entity_relation_graph.finalize()
                if hasattr(instance, 'doc_status'):
                    await instance.doc_status.finalize()
            except Exception as e:
                logger.warning(f"Error finalizing instance {key}: {e}")
            
            del self._instances[key]
            del self._last_access[key]
    
    async def cleanup_expired(self):
        """Remove all expired instances (can be called periodically)."""
        async with self._lock:
            now = datetime.now()
            expired_keys = [
                key for key, last_access in self._last_access.items()
                if (now - last_access) > self.ttl
            ]
            
            for key in expired_keys:
                logger.info(f"Cleaning up expired instance: tenant={key[0]}, project={key[1]}")
                await self._remove_instance(key)
    
    async def shutdown(self):
        """Shutdown all instances and cleanup resources."""
        logger.info("Shutting down LightRAG Instance Manager...")
        async with self._lock:
            keys = list(self._instances.keys())
            for key in keys:
                await self._remove_instance(key)
        logger.info("All instances cleaned up")
    
    def get_stats(self) -> dict:
        """Get statistics about the instance manager."""
        return {
            "active_instances": len(self._instances),
            "max_instances": self.max_instances,
            "ttl_minutes": self.ttl.total_seconds() / 60,
            "instances": [
                {
                    "tenant_id": key[0],
                    "project_id": key[1],
                    "last_access": self._last_access[key].isoformat()
                }
                for key in self._instances.keys()
            ]
        }
