variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "subnets" { type = list(string) }
variable "api_image" { type = string }
variable "dashboard_image" { type = string }

resource "aws_ecs_cluster" "deployos" {
  name = "deployos-${var.environment}"
}

resource "aws_ecs_task_definition" "api" {
  family                   = "deployos-api-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.api_image
      essential = true
      portMappings = [
        { containerPort = 8000, hostPort = 8000 }
      ]
      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "LOG_LEVEL", value = "INFO" }
      ]
    }
  ])
}

resource "aws_ecs_service" "api" {
  name            = "deployos-api"
  cluster         = aws_ecs_cluster.deployos.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnets
    assign_public_ip = true
  }
}
