"""
Multi-Tenant LightRAG Example

This example demonstrates how to use LightRAG with multi-tenant support,
allowing multiple companies and projects to share the same infrastructure
while maintaining complete data isolation.
"""

import asyncio
import os
from lightrag import LightRAG, QueryParam
from lightrag.llm import openai_complete_if_cache, openai_embedding

# Configure your OpenAI API
os.environ["OPENAI_API_KEY"] = "your-api-key-here"

# Multi-tenant configuration
WORKING_DIR = "./rag_storage"

async def example_single_tenant():
    """Example: Single tenant, single project"""
    print("\n=== Single Tenant Example ===")
    
    rag = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=openai_complete_if_cache,
        embedding_func=openai_embedding,
        # Multi-tenant identifiers
        tenant_id="acme_corp",
        project_id="sales_analytics",
        workspace="production"
    )
    
    # Insert documents
    print("Inserting documents...")
    await rag.ainsert("""
    ACME Corp Q4 Sales Report:
    - Total revenue: $5.2M
    - Top performing region: North America
    - Growth rate: 15% YoY
    - Key products: Widget Pro, Gadget Plus
    """)
    
    # Query
    print("\nQuerying...")
    result = await rag.aquery(
        "What was the total revenue?",
        param=QueryParam(mode="hybrid")
    )
    print(f"Result: {result}")


async def example_multiple_tenants():
    """Example: Multiple tenants with isolated data"""
    print("\n=== Multiple Tenants Example ===")
    
    # Tenant 1: ACME Corp
    rag_acme = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=openai_complete_if_cache,
        embedding_func=openai_embedding,
        tenant_id="acme_corp",
        project_id="hr_system",
        workspace="production"
    )
    
    # Tenant 2: TechStart Inc
    rag_techstart = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=openai_complete_if_cache,
        embedding_func=openai_embedding,
        tenant_id="techstart_inc",
        project_id="hr_system",
        workspace="production"
    )
    
    # Insert data for ACME Corp
    print("Inserting ACME Corp employee data...")
    await rag_acme.ainsert("""
    Employee: John Doe
    Department: Engineering
    Salary: $120,000
    Start Date: 2020-01-15
    """)
    
    # Insert data for TechStart Inc
    print("Inserting TechStart Inc employee data...")
    await rag_techstart.ainsert("""
    Employee: Jane Smith
    Department: Engineering
    Salary: $95,000
    Start Date: 2021-03-10
    """)
    
    # Query ACME Corp - should only see John Doe
    print("\nQuerying ACME Corp...")
    result_acme = await rag_acme.aquery(
        "List all engineering employees",
        param=QueryParam(mode="hybrid")
    )
    print(f"ACME Result: {result_acme}")
    
    # Query TechStart Inc - should only see Jane Smith
    print("\nQuerying TechStart Inc...")
    result_techstart = await rag_techstart.aquery(
        "List all engineering employees",
        param=QueryParam(mode="hybrid")
    )
    print(f"TechStart Result: {result_techstart}")


async def example_multiple_projects():
    """Example: Single tenant with multiple projects"""
    print("\n=== Multiple Projects Example ===")
    
    # Project 1: Customer Support
    rag_support = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=openai_complete_if_cache,
        embedding_func=openai_embedding,
        tenant_id="acme_corp",
        project_id="customer_support",
        workspace="production"
    )
    
    # Project 2: Product Documentation
    rag_docs = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=openai_complete_if_cache,
        embedding_func=openai_embedding,
        tenant_id="acme_corp",
        project_id="product_docs",
        workspace="production"
    )
    
    # Insert support tickets
    print("Inserting support tickets...")
    await rag_support.ainsert("""
    Ticket #1234: Customer reports login issues
    Priority: High
    Status: Open
    Assigned to: Support Team
    """)
    
    # Insert product docs
    print("Inserting product documentation...")
    await rag_docs.ainsert("""
    Widget Pro User Manual:
    1. Installation
    2. Configuration
    3. Troubleshooting
    """)
    
    # Query support project
    print("\nQuerying support project...")
    result_support = await rag_support.aquery(
        "What open tickets do we have?",
        param=QueryParam(mode="hybrid")
    )
    print(f"Support Result: {result_support}")
    
    # Query docs project
    print("\nQuerying docs project...")
    result_docs = await rag_docs.aquery(
        "How do I install Widget Pro?",
        param=QueryParam(mode="hybrid")
    )
    print(f"Docs Result: {result_docs}")


async def example_multiple_workspaces():
    """Example: Same tenant/project across different environments"""
    print("\n=== Multiple Workspaces Example ===")
    
    # Development environment
    rag_dev = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=openai_complete_if_cache,
        embedding_func=openai_embedding,
        tenant_id="acme_corp",
        project_id="main_app",
        workspace="development"
    )
    
    # Production environment
    rag_prod = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=openai_complete_if_cache,
        embedding_func=openai_embedding,
        tenant_id="acme_corp",
        project_id="main_app",
        workspace="production"
    )
    
    # Insert test data in development
    print("Inserting test data in development...")
    await rag_dev.ainsert("""
    Test Configuration:
    - Debug Mode: Enabled
    - Sample Data: 100 records
    - Test User: test@example.com
    """)
    
    # Insert production data
    print("Inserting production data...")
    await rag_prod.ainsert("""
    Production Configuration:
    - Debug Mode: Disabled
    - Active Users: 10,000
    - Uptime: 99.9%
    """)
    
    # Query development
    print("\nQuerying development...")
    result_dev = await rag_dev.aquery(
        "What is the debug mode status?",
        param=QueryParam(mode="hybrid")
    )
    print(f"Dev Result: {result_dev}")
    
    # Query production
    print("\nQuerying production...")
    result_prod = await rag_prod.aquery(
        "What is the debug mode status?",
        param=QueryParam(mode="hybrid")
    )
    print(f"Prod Result: {result_prod}")


async def example_data_migration():
    """Example: Migrating data between tenants/projects"""
    print("\n=== Data Migration Example ===")
    
    # Source: Old system
    rag_old = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=openai_complete_if_cache,
        embedding_func=openai_embedding,
        tenant_id="legacy_system",
        project_id="old_crm",
        workspace="production"
    )
    
    # Destination: New system
    rag_new = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=openai_complete_if_cache,
        embedding_func=openai_embedding,
        tenant_id="acme_corp",
        project_id="new_crm",
        workspace="production"
    )
    
    # Insert data in old system
    print("Inserting legacy data...")
    customer_data = """
    Customer: ABC Company
    Account Manager: John Doe
    Revenue: $500,000
    Contract End Date: 2024-12-31
    """
    await rag_old.ainsert(customer_data)
    
    # Migrate to new system (in production, you'd query and re-insert)
    print("Migrating to new system...")
    await rag_new.ainsert(customer_data)
    
    print("Migration complete!")
    
    # Verify in new system
    result = await rag_new.aquery(
        "Who is the account manager for ABC Company?",
        param=QueryParam(mode="hybrid")
    )
    print(f"Verification Result: {result}")


async def example_batch_operations():
    """Example: Batch operations across tenants"""
    print("\n=== Batch Operations Example ===")
    
    tenants = [
        ("company_a", "project_alpha"),
        ("company_b", "project_beta"),
        ("company_c", "project_gamma")
    ]
    
    # Initialize RAG instances for each tenant
    rag_instances = []
    for tenant_id, project_id in tenants:
        rag = LightRAG(
            working_dir=WORKING_DIR,
            llm_model_func=openai_complete_if_cache,
            embedding_func=openai_embedding,
            tenant_id=tenant_id,
            project_id=project_id,
            workspace="production"
        )
        rag_instances.append((tenant_id, project_id, rag))
    
    # Insert data for all tenants concurrently
    print("Inserting data for all tenants...")
    tasks = []
    for tenant_id, project_id, rag in rag_instances:
        data = f"Company: {tenant_id}, Project: {project_id}, Status: Active"
        tasks.append(rag.ainsert(data))
    
    await asyncio.gather(*tasks)
    print("Batch insert complete!")
    
    # Query all tenants concurrently
    print("\nQuerying all tenants...")
    query_tasks = []
    for tenant_id, project_id, rag in rag_instances:
        query_tasks.append(rag.aquery(
            "What is the project status?",
            param=QueryParam(mode="naive")
        ))
    
    results = await asyncio.gather(*query_tasks)
    
    # Display results
    for (tenant_id, project_id, _), result in zip(rag_instances, results):
        print(f"{tenant_id}/{project_id}: {result}")


async def main():
    """Run all examples"""
    
    # Uncomment the examples you want to run:
    
    # await example_single_tenant()
    # await example_multiple_tenants()
    # await example_multiple_projects()
    # await example_multiple_workspaces()
    # await example_data_migration()
    # await example_batch_operations()
    
    print("\n=== Examples Complete ===")
    print("Uncomment the examples you want to run in the main() function")


if __name__ == "__main__":
    # Ensure PostgreSQL is configured with multi-tenant support
    print("Multi-Tenant LightRAG Examples")
    print("=" * 50)
    print("\nPrerequisites:")
    print("1. PostgreSQL with Apache AGE extension installed")
    print("2. Migration script executed (001_add_multi_tenant_support.sql)")
    print("3. Environment variables configured:")
    print("   - POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, etc.")
    print("   - LIGHTRAG_GRAPH_STORAGE=PGGraphStorage")
    print("   - OPENAI_API_KEY or your LLM provider")
    print("\n" + "=" * 50)
    
    asyncio.run(main())
