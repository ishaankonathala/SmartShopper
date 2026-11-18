"""ORM models for SmartShopper domain entities."""

from app.models.product import Product
from app.models.amazon_catalogue_product import AmazonCatalogueProduct
from app.models.shopper_dna import ShopperDNA
from app.models.shopping_history import ShoppingHistory
from app.models.user_profile import UserProfile

__all__ = [
    "UserProfile",
    "ShopperDNA",
    "Product",
    "AmazonCatalogueProduct",
    "ShoppingHistory",
]
