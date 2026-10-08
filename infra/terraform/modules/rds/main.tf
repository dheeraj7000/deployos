variable "environment" { type = string }
variable "subnets" { type = list(string) }

resource "aws_db_subnet_group" "db_subnets" {
  name       = "deployos-db-${var.environment}"
  subnet_ids = var.subnets
}

resource "aws_db_instance" "postgres" {
  identifier          = "deployos-postgres-${var.environment}"
  engine              = "postgres"
  engine_version      = "16.1"
  instance_class      = "db.t4g.medium"
  allocated_storage   = 50
  max_allocated_storage = 200
  db_name             = "deployos"
  username            = "deployos_admin"
  manage_master_user_password = true
  db_subnet_group_name = aws_db_subnet_group.db_subnets.name
  skip_final_snapshot = true
}

output "endpoint" {
  value = aws_db_instance.postgres.endpoint
}
