# apps/core/management/commands/create_sample_data.py
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.products.models import Category, Product
from apps.authentication.models import CustomerProfile
from decimal import Decimal

Customer = get_user_model()


class Command(BaseCommand):
    help = 'Create sample data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample data...')
        
        # Create sample customer
        if not Customer.objects.filter(email='demo@example.com').exists():
            customer = Customer.objects.create_user(
                username='democustomer',
                email='demo@example.com',
                password='demo123',
                first_name='Demo',
                last_name='Customer',
                phone_number='+254712345678'
            )
            CustomerProfile.objects.create(customer=customer)
            self.stdout.write('✅ Created demo customer (demo@example.com / demo123)')
        
        # Create categories hierarchy
        categories_data = [
            {'name': 'All Products', 'slug': 'all-products', 'parent': None},
            {'name': 'Bakery', 'slug': 'bakery', 'parent': 'all-products'},
            {'name': 'Bread', 'slug': 'bread', 'parent': 'bakery'},
            {'name': 'Cookies', 'slug': 'cookies', 'parent': 'bakery'},
            {'name': 'Produce', 'slug': 'produce', 'parent': 'all-products'},
            {'name': 'Fruits', 'slug': 'fruits', 'parent': 'produce'},
            {'name': 'Vegetables', 'slug': 'vegetables', 'parent': 'produce'},
        ]
        
        created_categories = {}
        for cat_data in categories_data:
            if not Category.objects.filter(slug=cat_data['slug']).exists():
                parent = None
                if cat_data['parent']:
                    parent = created_categories.get(cat_data['parent'])
                
                category = Category.objects.create(
                    name=cat_data['name'],
                    slug=cat_data['slug'],
                    parent=parent,
                    description=f"{cat_data['name']} category"
                )
                created_categories[cat_data['slug']] = category
                self.stdout.write(f'✅ Created category: {category.name}')
        
        # Create sample products
        products_data = [
            {'name': 'White Bread', 'price': '150.00', 'sku': 'BRD001', 'category': 'bread'},
            {'name': 'Whole Wheat Bread', 'price': '180.00', 'sku': 'BRD002', 'category': 'bread'},
            {'name': 'Chocolate Cookies', 'price': '200.00', 'sku': 'COK001', 'category': 'cookies'},
            {'name': 'Oatmeal Cookies', 'price': '220.00', 'sku': 'COK002', 'category': 'cookies'},
            {'name': 'Red Apples', 'price': '300.00', 'sku': 'FRT001', 'category': 'fruits'},
            {'name': 'Bananas', 'price': '120.00', 'sku': 'FRT002', 'category': 'fruits'},
            {'name': 'Oranges', 'price': '250.00', 'sku': 'FRT003', 'category': 'fruits'},
            {'name': 'Carrots', 'price': '80.00', 'sku': 'VEG001', 'category': 'vegetables'},
            {'name': 'Tomatoes', 'price': '250.00', 'sku': 'VEG002', 'category': 'vegetables'},
            {'name': 'Onions', 'price': '150.00', 'sku': 'VEG003', 'category': 'vegetables'},
        ]
        
        for prod_data in products_data:
            if not Product.objects.filter(sku=prod_data['sku']).exists():
                category = Category.objects.get(slug=prod_data['category'])
                product = Product.objects.create(
                    name=prod_data['name'],
                    slug=prod_data['name'].lower().replace(' ', '-'),
                    description=f"Fresh {prod_data['name']} from our store",
                    price=Decimal(prod_data['price']),
                    sku=prod_data['sku'],
                    stock_quantity=100,
                    minimum_stock=10,
                    status='active'
                )
                product.categories.add(category)
                self.stdout.write(f'✅ Created product: {product.name} - KES {product.price}')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Sample data created successfully!'))
        self.stdout.write(self.style.SUCCESS('Demo customer: demo@example.com / demo123'))
        self.stdout.write(self.style.SUCCESS('Admin panel: http://127.0.0.1:8000/admin/'))
        self.stdout.write(self.style.SUCCESS('API docs: http://127.0.0.1:8000/swagger/'))
