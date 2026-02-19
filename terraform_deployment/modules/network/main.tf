locals {
  az_count = length(var.aws_availability_zones)

  # Each AZ will have 2 subnets (public + private)
  total_subnets = local.az_count * 2

  # Number of additional bits needed to split VPC into `total_subnets`
  newbits = ceil(log(local.total_subnets, 2))
}


resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr_block

  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = var.tags
}


# Public subnets
resource "aws_subnet" "public" {
  count = local.az_count

  availability_zone      = var.aws_availability_zones[count.index]
  cidr_block             = cidrsubnet(var.vpc_cidr_block, local.newbits, count.index * 2)
  vpc_id                 = aws_vpc.main.id
  map_public_ip_on_launch = true

  tags = merge(var.tags, { "Name" = "public-${count.index}" })

  lifecycle {
    ignore_changes = [
      availability_zone,
      cidr_block
    ]
  }
}

# Private subnets
resource "aws_subnet" "private" {
  count = local.az_count

  availability_zone = var.aws_availability_zones[count.index]
  cidr_block        = cidrsubnet(var.vpc_cidr_block, local.newbits, count.index * 2 + 1)
  vpc_id            = aws_vpc.main.id
  map_public_ip_on_launch = false

  tags = merge(var.tags, { "Name" = "private-${count.index}" })

  lifecycle {
    ignore_changes = [      
      availability_zone,
      cidr_block]
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge({ Name = var.name }, var.tags)
}


# Route the public subnet traffic through the IGW
resource "aws_route" "internet_access" {
    route_table_id         = aws_vpc.main.main_route_table_id
    destination_cidr_block = "0.0.0.0/0"
    gateway_id             = aws_internet_gateway.main.id
}


# Create a new route table for the private subnets, 
resource "aws_route_table" "private" {
    count  = length(var.aws_availability_zones)
    vpc_id = aws_vpc.main.id

}


variable "private_subnet_to_rt" {
  type = map(string)
  default = {
    "subnet-06884e5beb7fd2f8b" = "rtb-0365520b4a1559725"
    "subnet-0733fed6dff9e9f29" = "rtb-0170d75790e6ec02e"
  }
}

resource "aws_route_table_association" "private" {
  for_each      = var.private_subnet_to_rt
  subnet_id     = each.key
  route_table_id = each.value
}

# # Explicitly associate the newly created route tables to the private subnets (so they don't default to the main route table)
# resource "aws_route_table_association" "private" {
#     count          = length(var.aws_availability_zones)
#     subnet_id      = element(aws_subnet.private.*.id, count.index)
#     route_table_id = element(aws_route_table.private.*.id, count.index)
# }

resource "aws_security_group" "main" {
  name        = "vswir-plants_security_group"
  description = "security group for plants database"
  vpc_id = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"] # Canonical
}

# Create a security group for the bastion instance
resource "aws_security_group" "bastion_sg" {
  name        = "${var.name}-bastion-sg"
  description = "Security group for the bastion host"
  vpc_id      = aws_vpc.main.id

  // Allow SSH access from your IP address
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  // Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}

resource "aws_key_pair" "bastion-key" {
  key_name   = "${var.name}-bastion-key"
  public_key = file("~/.ssh/bastion-key.pub")  # Path to your public key file
  tags = var.tags
}

# Create a bastion instance

resource "aws_instance" "bastion_instance" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t2.micro" 
  subnet_id              = aws_subnet.public.*.id[0]
  vpc_security_group_ids         = [aws_security_group.bastion_sg.id]
  key_name               = "${var.name}-bastion-key"
  associate_public_ip_address = true
  iam_instance_profile = "SMCE_SSMAgent"

  tags = var.tags

  lifecycle {
  ignore_changes = [tags]
}
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"

  # Attach to your VPC's route tables
  route_table_ids =  concat([aws_vpc.main.main_route_table_id], aws_route_table.private[*].id)
}
