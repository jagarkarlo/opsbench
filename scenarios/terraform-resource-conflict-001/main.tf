resource "aws_subnet" "app_subnet" {
  vpc_id            = "vpc-0a1b2c3d"
  cidr_block        = "10.0.1.0/24"
  availability_zone = "us-east-1a"
}
