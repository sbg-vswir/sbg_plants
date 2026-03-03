# SQS Queue
resource "aws_sqs_queue" "pixels_queue" {
  name                      = "pixel-selection-queue"
  visibility_timeout_seconds = 900
  message_retention_seconds  = 86400
}

# Lambda IAM
resource "aws_iam_role" "lambda_role" {
  name = "pixel-selection-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda_sqs" {
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.pixels_queue.arn
      },
      {
        Effect = "Allow"
        Action = ["logs:*"]
        Resource = "*"
      }
    ]
  })
}

# Lambda Function
resource "aws_lambda_function" "producer" {
  function_name = "pixel-selection-producer"
  role          = aws_iam_role.lambda_role.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"

  filename         = "lambda.zip"
  source_code_hash = filebase64sha256("lambda.zip")

  environment {
    variables = {
      QUEUE_URL = aws_sqs_queue.pixels_queue.url
    }
  }
}

# Lambda API Gateway Integration
resource "aws_apigatewayv2_integration" "lambda" {
  api_id           = var.api_id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.producer.invoke_arn
}

resource "aws_apigatewayv2_route" "pixel_selection" {
  api_id    = var.api_id
  route_key = "POST /isofit/pixel-selection"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}


# ECS Cluster
resource "aws_ecs_cluster" "this" {
  name = "ISOFIT-Per-Pixel-Cluster"
}

# Fargate task execution role IAM
resource "aws_iam_role" "task_execution_role" {
  name = "ecsTaskExecutionRolePixel"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Task IAM
resource "aws_iam_role" "task_role" {
  name = "pixel-selection-worker-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "worker_policy" {
  role = aws_iam_role.task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.jobs.arn
      }
    ]
  })
}


# security groups
resource "aws_security_group" "worker" {
  name   = "pixel-worker-sg"
  vpc_id = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group_rule" "worker_to_db" {
  type                     = "egress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.worker.id
  source_security_group_id = var.db_security_group_id
}

# task definition
resource "aws_ecs_task_definition" "worker" {
  family                   = "pixel-selection-worker"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 1024 # 1 core
  memory                   = 1024 * 8 # 8GB
  network_mode             = "awsvpc"

  execution_role_arn = aws_iam_role.task_execution_role.arn
  task_role_arn      = aws_iam_role.task_role.arn

  container_definitions = jsonencode([
    {
      name  = "worker"
      image = var.ecr_image

      essential = true

      environment = [
        {
          name  = "QUEUE_URL"
          value = aws_sqs_queue.pixels_queue.url
          # db con stuff
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = "/ecs/pixel-worker"
          awslogs-region        = var.region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

# ECS Service
resource "aws_ecs_service" "worker" {
  name            = "pixel-worker"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 0

  capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 1
  }

  network_configuration {
    subnets         = var.private_subnets
    security_groups = [aws_security_group.worker.id]
  }

  enable_execute_command = true
}

# autoscaling
resource "aws_appautoscaling_target" "ecs" {
  max_capacity       = 10 # max number of tasks
  min_capacity       = 0
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# autoscaling based on queue depth
resource "aws_cloudwatch_metric_alarm" "queue_high" {
  alarm_name          = "pixel-queue-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 10

  metric_name = "ApproximateNumberOfMessagesVisible"
  namespace   = "AWS/SQS"
  period      = 60
  statistic   = "Average"

  dimensions = {
    QueueName = aws_sqs_queue.pixels_queue.name
  }
}

resource "aws_appautoscaling_policy" "scale_up" {
  name               = "scale-up"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  step_scaling_policy_configuration {
    adjustment_type = "ChangeInCapacity"

    step_adjustment {
      metric_interval_lower_bound = 0
      scaling_adjustment          = 5
    }

    cooldown = 60
  }
}
