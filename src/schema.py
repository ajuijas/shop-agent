
# ============================================================================
# DATABASE SCHEMA
# ============================================================================

DB_SCHEMA = """
-- Table: products
-- Columns: Product ID, Product Title, Category, Price (INR), Features, Description
CREATE TABLE public.products (
  Product ID bigint NOT NULL,
  Product Title text,
  Category text,
  Price (INR) bigint,
  Features text,
  Description text,
  CONSTRAINT products_pkey PRIMARY KEY (Product ID)
);
"""

SCHEMA_MAPPER = {
    "table" : "products",
    "id" : "Product ID",
    "title" : "Product Title",
    "category" : "Category",
    "brand" : "Brand",
    "price" : "Price (INR)",
    "features" : "Features",
    "description" : "Description"
}

# DB_SCHEMA = """
# CREATE TABLE public.100kproducts (
#   Index bigint NOT NULL,
#   Name text,
#   Description text,
#   Brand text,
#   Category text,
#   Price bigint,
#   Currency text,
#   Stock bigint,
#   EAN bigint,
#   Color text,
#   Size text,
#   Availability text,
#   Internal ID bigint NOT NULL,
#   CONSTRAINT 100kproducts_pkey PRIMARY KEY (Index)
# );
# """

# SCHEMA_MAPPER = {
#     "table" : "100kproducts",
#     "id" : "Index",
#     "title" : "Name",
#     "category" : "Category",
#     "brand" : "Brand",
#     "price" : "Price",
#     "features" : "Features",
#     "description" : "Description"
# }
