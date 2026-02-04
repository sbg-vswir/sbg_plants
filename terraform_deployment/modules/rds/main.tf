
resource "aws_db_subnet_group" "database_subnet_group" {
  name       = "${var.name}_subnet_group"
  subnet_ids = var.private_subnet_ids

  tags = var.tags

}

resource "aws_security_group" "database_sg" {
  name        = "${var.name}_security_group"
  description = "security group for plants database"
  vpc_id      = var.vpc_id

}

resource "aws_security_group_rule" "database_access" {
  type              = "ingress"
  from_port         = var.db_port
  to_port           = var.db_port
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr_block]
  security_group_id = aws_security_group.database_sg.id
}

resource "aws_db_instance" "default" {
  allocated_storage      = 200
  identifier = "${var.name}-instance"
  db_name               = var.db_name
  engine                = "postgres"
  engine_version        = "18.1"
  instance_class        = "db.t3.small"
  username              = "dbadmin"
  password              = var.db_password
  vpc_security_group_ids = [aws_security_group.database_sg.id]
  port                  = var.db_port
  availability_zone     = "us-west-2a" 
  db_subnet_group_name  = aws_db_subnet_group.database_subnet_group.name
  apply_immediately     = true
  publicly_accessible    = false

  backup_retention_period = 30 
  backup_window           = "03:00-04:00"

  skip_final_snapshot     = false
  final_snapshot_identifier = "${var.name}-final-snapshot"

  multi_az                = false  
  storage_encrypted       = false  
  tags = var.tags

  # Lifecycle protection
  lifecycle {
    prevent_destroy = true
  }
}