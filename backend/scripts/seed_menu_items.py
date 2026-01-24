"""
Seed script for populating menu items for Lexi's Gourmet Sandwiches.

This script creates initial menu items with realistic gourmet sandwich data.
Prices are in paise (₹1 = 100 paise).
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import get_settings
from app.models.menu_item import (
    MenuItemCreate,
    IngredientTag,
    PrepType,
)


# Menu items data for Lexi's Gourmet Sandwiches
MENU_ITEMS = [
    # Classic Sandwiches
    {
        "name": "Classic Turkey Club",
        "description": "Sliced roasted turkey breast with crispy bacon, fresh lettuce, tomatoes, and mayo on toasted multigrain bread.",
        "price": 35000,  # ₹350.00
        "category": "Classic Sandwiches",
        "tags": [IngredientTag.TURKEY, IngredientTag.BACON, IngredientTag.LETTUCE, IngredientTag.TOMATOES, IngredientTag.MAYONNAISE, IngredientTag.BREAD],
        "prep_type": PrepType.COLD,
        "is_available": True,
    },
    {
        "name": "Italian Deli",
        "description": "Genoa salami, prosciutto, provolone cheese, roasted peppers, and arugula with balsamic glaze on ciabatta.",
        "price": 42000,  # ₹420.00
        "category": "Classic Sandwiches",
        "tags": [IngredientTag.SALAMI, IngredientTag.PROSCIUTTO, IngredientTag.PROVOLONE, IngredientTag.PEPPERS, IngredientTag.ARUGULA, IngredientTag.BREAD],
        "prep_type": PrepType.COLD,
        "is_available": True,
    },
    {
        "name": "Grilled Chicken Caesar",
        "description": "Grilled chicken breast with romaine lettuce, parmesan cheese, and house-made Caesar dressing on focaccia.",
        "price": 38000,  # ₹380.00
        "category": "Classic Sandwiches",
        "tags": [IngredientTag.CHICKEN, IngredientTag.LETTUCE, IngredientTag.PARMESAN, IngredientTag.BREAD],
        "prep_type": PrepType.GRILL,
        "is_available": True,
    },
    {
        "name": "Roast Beef & Cheddar",
        "description": "Tender roast beef with aged cheddar, caramelized onions, and horseradish mayo on sourdough.",
        "price": 45000,  # ₹450.00
        "category": "Classic Sandwiches",
        "tags": [IngredientTag.BEEF, IngredientTag.CHEDDAR, IngredientTag.ONIONS, IngredientTag.MAYONNAISE, IngredientTag.BREAD],
        "prep_type": PrepType.COLD,
        "is_available": True,
    },
    
    # Gourmet Specials
    {
        "name": "Truffle Mushroom Melt",
        "description": "Sautéed wild mushrooms with truffle oil, melted Swiss cheese, and caramelized onions on artisanal bread.",
        "price": 48000,  # ₹480.00
        "category": "Gourmet Specials",
        "tags": [IngredientTag.MUSHROOMS, IngredientTag.SWISS, IngredientTag.ONIONS, IngredientTag.BREAD, IngredientTag.BUTTER],
        "prep_type": PrepType.SAUTE,
        "is_available": True,
    },
    {
        "name": "Mediterranean Veggie",
        "description": "Grilled vegetables, feta cheese, olives, sun-dried tomatoes, and pesto on herb focaccia.",
        "price": 36000,  # ₹360.00
        "category": "Gourmet Specials",
        "tags": [IngredientTag.PEPPERS, IngredientTag.FETA, IngredientTag.OLIVES, IngredientTag.TOMATOES, IngredientTag.PESTO, IngredientTag.BREAD],
        "prep_type": PrepType.GRILL,
        "is_available": True,
    },
    {
        "name": "BBQ Pulled Pork",
        "description": "Slow-cooked pulled pork with house BBQ sauce, coleslaw, and pickles on brioche bun.",
        "price": 40000,  # ₹400.00
        "category": "Gourmet Specials",
        "tags": [IngredientTag.PORK, IngredientTag.PICKLES, IngredientTag.BREAD],
        "prep_type": PrepType.OVEN,
        "is_available": True,
    },
    {
        "name": "Lobster Roll",
        "description": "Fresh lobster meat with lemon aioli, celery, and chives on a buttered brioche roll.",
        "price": 65000,  # ₹650.00
        "category": "Gourmet Specials",
        "tags": [IngredientTag.SHRIMP, IngredientTag.AIOLI, IngredientTag.BREAD, IngredientTag.BUTTER],
        "prep_type": PrepType.COLD,
        "is_available": True,
    },
    
    # Hot Sandwiches
    {
        "name": "Philly Cheesesteak",
        "description": "Thinly sliced beef with sautéed onions, peppers, and melted provolone on a hoagie roll.",
        "price": 42000,  # ₹420.00
        "category": "Hot Sandwiches",
        "tags": [IngredientTag.BEEF, IngredientTag.ONIONS, IngredientTag.PEPPERS, IngredientTag.PROVOLONE, IngredientTag.BREAD],
        "prep_type": PrepType.SAUTE,
        "is_available": True,
    },
    {
        "name": "Crispy Chicken Tenders",
        "description": "Hand-breaded chicken tenders with honey mustard, lettuce, and pickles on a brioche bun.",
        "price": 38000,  # ₹380.00
        "category": "Hot Sandwiches",
        "tags": [IngredientTag.CHICKEN, IngredientTag.LETTUCE, IngredientTag.PICKLES, IngredientTag.MUSTARD, IngredientTag.HONEY, IngredientTag.BREAD],
        "prep_type": PrepType.FRY,
        "is_available": True,
    },
    {
        "name": "Reuben",
        "description": "Corned beef, Swiss cheese, sauerkraut, and Russian dressing on grilled rye bread.",
        "price": 44000,  # ₹440.00
        "category": "Hot Sandwiches",
        "tags": [IngredientTag.BEEF, IngredientTag.SWISS, IngredientTag.BREAD],
        "prep_type": PrepType.GRILL,
        "is_available": True,
    },
    
    # Vegetarian Options
    {
        "name": "Caprese Panini",
        "description": "Fresh mozzarella, tomatoes, basil, and balsamic glaze pressed on ciabatta.",
        "price": 32000,  # ₹320.00
        "category": "Vegetarian Options",
        "tags": [IngredientTag.MOZZARELLA, IngredientTag.TOMATOES, IngredientTag.BASIL, IngredientTag.BREAD],
        "prep_type": PrepType.OVEN,
        "is_available": True,
    },
    {
        "name": "Avocado & Hummus",
        "description": "Mashed avocado, hummus, sprouts, cucumber, and lemon on whole grain bread.",
        "price": 30000,  # ₹300.00
        "category": "Vegetarian Options",
        "tags": [IngredientTag.AVOCADO, IngredientTag.BREAD],
        "prep_type": PrepType.COLD,
        "is_available": True,
    },
    {
        "name": "Grilled Portobello",
        "description": "Marinated portobello mushroom with roasted red peppers, goat cheese, and arugula on focaccia.",
        "price": 35000,  # ₹350.00
        "category": "Vegetarian Options",
        "tags": [IngredientTag.MUSHROOMS, IngredientTag.PEPPERS, IngredientTag.ARUGULA, IngredientTag.BREAD],
        "prep_type": PrepType.GRILL,
        "is_available": True,
    },
    
    # Sides
    {
        "name": "Sweet Potato Fries",
        "description": "Crispy sweet potato fries served with chipotle aioli.",
        "price": 18000,  # ₹180.00
        "category": "Sides",
        "tags": [IngredientTag.AIOLI],
        "prep_type": PrepType.FRY,
        "is_available": True,
    },
    {
        "name": "House Salad",
        "description": "Mixed greens with cherry tomatoes, cucumbers, red onions, and house vinaigrette.",
        "price": 20000,  # ₹200.00
        "category": "Sides",
        "tags": [IngredientTag.LETTUCE, IngredientTag.TOMATOES, IngredientTag.ONIONS],
        "prep_type": PrepType.COLD,
        "is_available": True,
    },
    {
        "name": "Coleslaw",
        "description": "Creamy coleslaw with cabbage, carrots, and our signature dressing.",
        "price": 15000,  # ₹150.00
        "category": "Sides",
        "tags": [IngredientTag.CREAM],
        "prep_type": PrepType.COLD,
        "is_available": True,
    },
    
    # Beverages
    {
        "name": "Fresh Lemonade",
        "description": "House-made lemonade with fresh lemons and a hint of mint.",
        "price": 12000,  # ₹120.00
        "category": "Beverages",
        "tags": [],
        "prep_type": PrepType.BEVERAGE,
        "is_available": True,
    },
    {
        "name": "Iced Tea",
        "description": "Refreshing iced tea with lemon slice.",
        "price": 10000,  # ₹100.00
        "category": "Beverages",
        "tags": [],
        "prep_type": PrepType.BEVERAGE,
        "is_available": True,
    },
    {
        "name": "Craft Soda",
        "description": "Selection of artisanal craft sodas.",
        "price": 15000,  # ₹150.00
        "category": "Beverages",
        "tags": [],
        "prep_type": PrepType.BEVERAGE,
        "is_available": True,
    },
]


async def seed_menu_items(force: bool = False):
    """
    Seed menu items into the database.
    
    Args:
        force: If True, skip confirmation prompt when items already exist.
    """
    settings = get_settings()
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.DB_NAME]
    collection = db.menu_items
    
    print("🌱 Starting menu items seed...")
    print(f"📊 Found {len(MENU_ITEMS)} menu items to seed")
    
    # Check if items already exist
    existing_count = await collection.count_documents({})
    if existing_count > 0:
        print(f"⚠️  Warning: Found {existing_count} existing menu items in database.")
        if not force:
            response = input("Do you want to continue? This will add new items. (y/n): ")
            if response.lower() != 'y':
                print("❌ Seed cancelled.")
                client.close()
                return
        else:
            print("ℹ️  Force mode: Continuing without confirmation...")
    
    # Insert menu items
    inserted_count = 0
    for item_data in MENU_ITEMS:
        try:
            menu_item = MenuItemCreate(**item_data)
            from datetime import datetime, timezone
            
            item_doc = {
                "name": menu_item.name,
                "description": menu_item.description,
                "price": menu_item.price,
                "category": menu_item.category,
                "tags": [tag.value for tag in menu_item.tags],
                "prep_type": menu_item.prep_type.value,
                "is_available": menu_item.is_available,
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            
            result = await collection.insert_one(item_doc)
            inserted_count += 1
            print(f"✅ Inserted: {menu_item.name}")
        except Exception as e:
            print(f"❌ Error inserting {item_data.get('name', 'unknown')}: {e}")
    
    print(f"\n🎉 Seed complete! Inserted {inserted_count} menu items.")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed menu items into the database")
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Skip confirmation prompt when items already exist"
    )
    args = parser.parse_args()
    asyncio.run(seed_menu_items(force=args.force))
