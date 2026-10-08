terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

module "ecs" {
  source          = "../../modules/ecs"
  environment     = "prod"
  vpc_id          = "vpc-prod123"
  subnets         = ["subnet-prod1", "subnet-prod2"]
  api_image       = "123456789012.dkr.ecr.us-east-1.amazonaws.com/deployos-api:latest"
  dashboard_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/deployos-dashboard:latest"
}

module "rds" {
  source      = "../../modules/rds"
  environment = "prod"
  subnets     = ["subnet-prod1", "subnet-prod2"]
}

module "redis" {
  source      = "../../modules/redis"
  environment = "prod"
  subnets     = ["subnet-prod1", "subnet-prod2"]
}
