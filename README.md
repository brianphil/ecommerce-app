# E-commerce Backend API

A comprehensive Django-based e-commerce backend system with hierarchical product categories, order management, OpenID Connect authentication, and integrated SMS/Email notifications.

## Features

### Core Functionality

- **Hierarchical Product Categories**: Unlimited depth category structure using MPTT
- **Product Management**: Complete product catalog with images, reviews, and inventory tracking
- **Order Processing**: Full order lifecycle with status tracking and notifications
- **Shopping Cart**: Persistent cart management for customers
- **Authentication**: OpenID Connect integration for secure customer access

### Integrations

- **SMS Notifications**: Africa's Talking SMS gateway for order updates
- **Email Notifications**: SMTP email notifications for customers and administrators
- **Payment Ready**: Designed for easy payment gateway integration

### Technical Features

- **RESTful API**: Django REST Framework with comprehensive endpoints
- **Background Tasks**: Celery for asynchronous processing
- **Caching**: Redis for session management and task queuing
- **Database**: PostgreSQL with optimized queries
- **Documentation**: Auto-generated API documentation with Swagger/OpenAPI
- **Testing**: Comprehensive test coverage with pytest
- **CI/CD**: GitHub Actions pipeline with automated testing and deployment
- **Containerization**: Docker and Kubernetes deployment ready

## Requirements

- Python 3.11+
- PostgreSQL 13+
- Redis 6+
- Docker & Docker Compose (for containerized deployment)
- Kubernetes (for production deployment)

## Installation & Setup

### Local Development

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-username/ecommerce-backend.git
   cd ecommerce-backend
   ```

2. **Create virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Database Setup**

   ```bash
   # Ensure PostgreSQL is running
   createdb ecommerce_db
   python manage.py migrate
   python manage.py createsuperuser
   ```

6. **Load Initial Data**

   ```bash
   python manage.py loaddata fixtures/initial_categories.json
   python manage.py loaddata fixtures/sample_products.json
   ```

7. **Start Development Server**

   ```bash
   # Terminal 1: Start Django
   python manage.py runserver

   # Terminal 2: Start Celery Worker
   celery -A ecommerce worker -l info

   # Terminal 3: Start Celery Beat
   celery -A ecommerce beat -l info
   ```

### Docker Development

1. **Start all services**

   ```bash
   docker-compose up -d
   ```

2. **Run migrations**

   ```bash
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py createsuperuser
   ```

3. **Load sample data**
   ```bash
   docker-compose exec web python manage.py loaddata fixtures/initial_data.json
   ```

## API Documentation

Once the server is running, access the API documentation at:

- **Swagger UI**: http://localhost:8000/swagger/
- **ReDoc**: http://localhost:8000/redoc/
- **Raw Schema**: http://localhost:8000/swagger.json

## Authentication

The API uses OAuth2 with OpenID Connect for authentication.

### Getting Access Token

```bash
POST /api/v1/auth/customers/login/
Content-Type: application/json

{
    "email": "customer@example.com",
    "password": "password123"
}
```

**Response:**

```json
{
  "access_token": "your-access-token",
  "refresh_token": "your-refresh-token",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "read write",
  "customer": {
    "id": 1,
    "email": "customer@example.com",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

### Using the Token

Include the token in the Authorization header:

```bash
Authorization: Bearer your-access-token
```

## API Endpoints

### Authentication

- `POST /api/v1/auth/customers/register/` - Customer registration
- `POST /api/v1/auth/customers/login/` - Customer login
- `POST /api/v1/auth/customers/logout/` - Customer logout
- `GET /api/v1/auth/customers/profile/` - Get profile
- `PATCH /api/v1/auth/customers/update_profile/` - Update profile

### Product Management

- `GET /api/v1/products/categories/` - List categories
- `GET /api/v1/products/categories/tree/` - Category tree structure
- `GET /api/v1/products/categories/{slug}/average_price/` - Average price by category
- `GET /api/v1/products/products/` - List products
- `POST /api/v1/products/products/bulk_create/` - Bulk upload products
- `GET /api/v1/products/products/featured/` - Featured products
- `GET /api/v1/products/reviews/` - Product reviews

### Order Management

- `GET /api/v1/orders/orders/` - List customer orders
- `POST /api/v1/orders/orders/` - Create new order
- `GET /api/v1/orders/orders/{id}/` - Order details
- `POST /api/v1/orders/orders/{id}/cancel/` - Cancel order
- `GET /api/v1/orders/orders/{id}/tracking/` - Order tracking

### Shopping Cart

- `GET /api/v1/orders/cart/` - Get cart contents
- `POST /api/v1/orders/cart/add_item/` - Add item to cart
- `PATCH /api/v1/orders/cart/update_quantity/` - Update item quantity
- `DELETE /api/v1/orders/cart/remove_item/` - Remove item from cart
- `DELETE /api/v1/orders/cart/clear/` - Clear cart

## Database Schema

### Key Models

#### Categories (Hierarchical)

```python
class Category(MPTTModel):
    name = CharField(max_length=100)
    slug = SlugField(max_length=100)
    parent = TreeForeignKey('self')
    # Supports unlimited depth hierarchy
```

#### Products

```python
class Product(Model):
    name = CharField(max_length=200)
    categories = ManyToManyField(Category)
    price = DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = PositiveIntegerField()
    # Full product catalog features
```

#### Orders

```python
class Order(Model):
    customer = ForeignKey(Customer)
    status = CharField(choices=STATUS_CHOICES)
    total_amount = DecimalField(max_digits=10, decimal_places=2)
    # Complete order management
```

## Notifications

### SMS Notifications (Africa's Talking)

Configure in your `.env`:

```env
AFRICAS_TALKING_USERNAME=your_username
AFRICAS_TALKING_API_KEY=your_api_key
AFRICAS_TALKING_FROM=your_sender_id
```

**Automatic SMS sent for:**

- Order confirmation
- Order status updates
- Shipping notifications

### Email Notifications

Configure SMTP in your `.env`:

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
ADMIN_EMAIL=admin@yourstore.com
```

**Automatic emails sent for:**

- Order confirmations to customers
- Order notifications to administrators
- Low stock alerts

## Testing

### Run Tests

```bash
# Run all tests
python manage.py test

# Run with coverage
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report
```

### Test Categories

- **Unit Tests**: Model and utility function testing
- **API Tests**: Endpoint testing with authentication
- **Integration Tests**: Order flow and notification testing

## Deployment

### Docker Production

1. **Build and deploy**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

### Kubernetes Deployment

1. **Create secrets**

   ```bash
   kubectl create secret generic ecommerce-secrets \
     --from-literal=secret-key=your-secret-key \
     --from-literal=db-password=your-db-password \
     --from-literal=africastalking-api-key=your-api-key
   ```

2. **Deploy**

   ```bash
   kubectl apply -f k8s/
   ```

3. **Run migrations**
   ```bash
   kubectl exec deployment/ecommerce-backend -- python manage.py migrate
   ```

### Environment Variables

| Variable                   | Description                      | Required |
| -------------------------- | -------------------------------- | -------- |
| `SECRET_KEY`               | Django secret key                | Yes      |
| `DEBUG`                    | Debug mode (False in production) | No       |
| `DB_HOST`                  | PostgreSQL host                  | Yes      |
| `DB_NAME`                  | Database name                    | Yes      |
| `DB_USER`                  | Database user                    | Yes      |
| `DB_PASSWORD`              | Database password                | Yes      |
| `REDIS_URL`                | Redis connection URL             | Yes      |
| `AFRICAS_TALKING_USERNAME` | SMS gateway username             | No       |
| `AFRICAS_TALKING_API_KEY`  | SMS gateway API key              | No       |
| `EMAIL_HOST_USER`          | SMTP email username              | No       |
| `EMAIL_HOST_PASSWORD`      | SMTP email password              | No       |
| `ADMIN_EMAIL`              | Administrator email              | Yes      |

## Performance & Monitoring

### Database Optimizations

- Indexed fields for fast queries
- Select/prefetch related for N+1 prevention
- Database connection pooling

### Caching Strategy

- Redis for session storage
- Query result caching for category trees
- Product image caching

### Monitoring

- Built-in Django admin for data management
- Celery monitoring for background tasks
- Health check endpoints for Kubernetes

## Security Features

### Authentication & Authorization

- OAuth2 with OpenID Connect
- Token-based authentication
- Permission-based access control

### Data Protection

- Password hashing with Django's built-in system
- CSRF protection enabled
- SQL injection prevention via ORM

### API Security

- Rate limiting (configurable)
- CORS configuration
- Secure headers middleware

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Write comprehensive tests
- Update documentation for new features
- Use conventional commit messages

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support and questions:

- Create an issue in the GitHub repository
- Email: support@yourstore.com
- Documentation: [Project Wiki](https://github.com/your-username/ecommerce-backend/wiki)

## Acknowledgments

- **Django REST Framework** for the excellent API framework
- **Africa's Talking** for SMS gateway services
- **PostgreSQL** for robust database capabilities
- **Celery** for background task processing
- **Docker** and **Kubernetes** for containerization and orchestration

---

Built with ❤️ for Savannah Informatics Backend Developer Assessment
