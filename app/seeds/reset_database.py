import asyncio
from app.seeds.seed_contracts_workflows import seed_production_contracts_and_workflows


async def main():
    print("==================================================")
    print("  CLEAN DATABASE RESET & SEEDING (SINGLE WORKFLOW)")
    print("==================================================")
    await seed_production_contracts_and_workflows()
    print("\n🎉 DATABASE RESET & SEEDING COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(main())
