variable "environment" { type = string }
variable "subnets" { type = list(string) }

resource "aws_elasticache_subnet_group" "redis_subnets" {
  name       = "deployos-redis-${var.environment}"
  subnet_ids = var.subnets
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "deployos-redis-${var.environment}"
  engine               = "redis"
  node_type            = "cache.t4g.small"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.redis_subnets.name
}

output "endpoint" {
  value = aws_elasticache_cluster.redis.cache_nodes[0].address
}
