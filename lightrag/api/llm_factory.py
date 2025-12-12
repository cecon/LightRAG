"""
LLM Provider Factory Functions
Creates LLM functions for different providers based on database configurations
"""

from typing import Callable, Any, Dict, Optional
from lightrag.utils import logger


def create_openai_llm_func(
    api_key: str,
    model: str,
    base_url: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4000,
    **kwargs
) -> Callable:
    """
    Create OpenAI LLM function
    
    Args:
        api_key: OpenAI API key
        model: Model name (e.g., "gpt-4-turbo-preview")
        base_url: Optional custom base URL
        temperature: Temperature parameter
        max_tokens: Maximum tokens
        
    Returns:
        Async LLM completion function
    """
    from lightrag.llm.openai import openai_complete_if_cache
    
    async def llm_func(
        prompt: str,
        system_prompt: Optional[str] = None,
        history_messages: Optional[list] = None,
        **func_kwargs
    ) -> str:
        return await openai_complete_if_cache(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            **func_kwargs
        )
    
    logger.info(f"Created OpenAI LLM function: model={model}, base_url={base_url}")
    return llm_func


def create_ollama_llm_func(
    model: str,
    base_url: str = "http://localhost:11434",
    temperature: float = 0.7,
    max_tokens: int = 4000,
    **kwargs
) -> Callable:
    """
    Create Ollama LLM function (local models)
    
    Args:
        model: Model name (e.g., "llama2", "mistral")
        base_url: Ollama server URL
        temperature: Temperature parameter
        max_tokens: Maximum tokens
        
    Returns:
        Async LLM completion function
    """
    from lightrag.llm.ollama import ollama_model_complete
    
    async def llm_func(
        prompt: str,
        system_prompt: Optional[str] = None,
        history_messages: Optional[list] = None,
        **func_kwargs
    ) -> str:
        return await ollama_model_complete(
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            model=model,
            host=base_url,
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            **func_kwargs
        )
    
    logger.info(f"Created Ollama LLM function: model={model}, host={base_url}")
    return llm_func


def create_azure_openai_llm_func(
    api_key: str,
    model: str,
    base_url: str,
    temperature: float = 0.7,
    max_tokens: int = 4000,
    additional_config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Callable:
    """
    Create Azure OpenAI LLM function
    
    Args:
        api_key: Azure OpenAI API key
        model: Model name
        base_url: Azure OpenAI endpoint
        temperature: Temperature parameter
        max_tokens: Maximum tokens
        additional_config: Additional Azure-specific config (api_version, deployment_name)
        
    Returns:
        Async LLM completion function
    """
    from lightrag.llm.azure import azure_openai_complete
    
    api_version = (additional_config or {}).get("api_version", "2023-05-15")
    deployment_name = (additional_config or {}).get("deployment_name", model)
    
    async def llm_func(
        prompt: str,
        system_prompt: Optional[str] = None,
        history_messages: Optional[list] = None,
        **func_kwargs
    ) -> str:
        return await azure_openai_complete(
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            model=model,
            deployment_name=deployment_name,
            api_key=api_key,
            base_url=base_url,
            api_version=api_version,
            temperature=temperature,
            max_tokens=max_tokens,
            **func_kwargs
        )
    
    logger.info(f"Created Azure OpenAI LLM function: model={model}, endpoint={base_url}")
    return llm_func


def create_openai_compatible_llm_func(
    api_key: Optional[str],
    model: str,
    base_url: str,
    temperature: float = 0.7,
    max_tokens: int = 4000,
    **kwargs
) -> Callable:
    """
    Create OpenAI-compatible LLM function (for any OpenAI-compatible API)
    
    Args:
        api_key: API key (optional for some providers)
        model: Model name
        base_url: API endpoint URL
        temperature: Temperature parameter
        max_tokens: Maximum tokens
        
    Returns:
        Async LLM completion function
    """
    from lightrag.llm.openai import openai_complete_if_cache
    
    async def llm_func(
        prompt: str,
        system_prompt: Optional[str] = None,
        history_messages: Optional[list] = None,
        **func_kwargs
    ) -> str:
        return await openai_complete_if_cache(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            api_key=api_key or "dummy",  # Some providers don't need API key
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            **func_kwargs
        )
    
    logger.info(f"Created OpenAI-compatible LLM function: model={model}, base_url={base_url}")
    return llm_func


def create_embedding_func(
    provider: str,
    api_key: Optional[str],
    model: str,
    base_url: Optional[str] = None,
    **kwargs
) -> Callable:
    """
    Create embedding function based on provider
    
    Args:
        provider: Provider type (openai, azure_openai, ollama, etc.)
        api_key: API key
        model: Embedding model name
        base_url: Optional base URL
        
    Returns:
        Async embedding function
    """
    if provider == "openai":
        from lightrag.llm.openai import openai_embedding
        
        async def embed_func(texts: list[str]) -> list[list[float]]:
            return await openai_embedding(
                texts=texts,
                model=model,
                api_key=api_key,
                base_url=base_url
            )
        
        logger.info(f"Created OpenAI embedding function: model={model}")
        return embed_func
    
    elif provider == "azure_openai":
        from lightrag.llm.azure import azure_openai_embedding
        
        async def embed_func(texts: list[str]) -> list[list[float]]:
            return await azure_openai_embedding(
                texts=texts,
                model=model,
                api_key=api_key,
                base_url=base_url
            )
        
        logger.info(f"Created Azure OpenAI embedding function: model={model}")
        return embed_func
    
    elif provider == "ollama":
        from lightrag.llm.ollama import ollama_embedding
        
        async def embed_func(texts: list[str]) -> list[list[float]]:
            return await ollama_embedding(
                texts=texts,
                embed_model=model,
                host=base_url or "http://localhost:11434"
            )
        
        logger.info(f"Created Ollama embedding function: model={model}")
        return embed_func
    
    elif provider == "openai_compatible":
        from lightrag.llm.openai import openai_embedding
        
        async def embed_func(texts: list[str]) -> list[list[float]]:
            return await openai_embedding(
                texts=texts,
                model=model,
                api_key=api_key or "dummy",
                base_url=base_url
            )
        
        logger.info(f"Created OpenAI-compatible embedding function: model={model}")
        return embed_func
    
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")


def create_llm_from_config(config: Dict[str, Any]) -> Callable:
    """
    Create LLM function from database configuration
    
    Args:
        config: Configuration dict with provider, api_key, model_name, etc.
        
    Returns:
        Async LLM completion function
    """
    provider = config.get("provider")
    
    if provider == "openai":
        return create_openai_llm_func(
            api_key=config["api_key"],
            model=config["model_name"],
            base_url=config.get("base_url"),
            temperature=float(config.get("temperature", 0.7)),
            max_tokens=config.get("max_tokens", 4000)
        )
    
    elif provider == "azure_openai":
        return create_azure_openai_llm_func(
            api_key=config["api_key"],
            model=config["model_name"],
            base_url=config["base_url"],
            temperature=float(config.get("temperature", 0.7)),
            max_tokens=config.get("max_tokens", 4000),
            additional_config=config.get("additional_config")
        )
    
    elif provider == "ollama":
        return create_ollama_llm_func(
            model=config["model_name"],
            base_url=config.get("base_url", "http://localhost:11434"),
            temperature=float(config.get("temperature", 0.7)),
            max_tokens=config.get("max_tokens", 4000)
        )
    
    elif provider == "openai_compatible":
        return create_openai_compatible_llm_func(
            api_key=config.get("api_key"),
            model=config["model_name"],
            base_url=config["base_url"],
            temperature=float(config.get("temperature", 0.7)),
            max_tokens=config.get("max_tokens", 4000)
        )
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def create_embedding_from_config(config: Dict[str, Any]) -> Optional[Callable]:
    """
    Create embedding function from database configuration
    
    Args:
        config: Configuration dict with embedding settings
        
    Returns:
        Async embedding function or None if no embedding config
    """
    if not config.get("embedding_model"):
        return None
    
    return create_embedding_func(
        provider=config.get("provider"),
        api_key=config.get("embedding_api_key") or config.get("api_key"),
        model=config["embedding_model"],
        base_url=config.get("embedding_base_url") or config.get("base_url")
    )
