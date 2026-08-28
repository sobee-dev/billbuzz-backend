from .models import Product


def get_or_create_product(business, name, unit_price=0):
    name = name.strip()
    product = Product.objects.filter(business=business, name__iexact=name).first()
    if product:
        return product
    return Product.objects.create(
        business=business, 
        name=name, 
        unit_price=unit_price,
        sku=None,
    )