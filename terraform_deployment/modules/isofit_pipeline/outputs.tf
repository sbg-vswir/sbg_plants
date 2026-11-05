output "slim_job_queue" {
  value = aws_batch_job_queue.worker_slim.name
}

output "slim_job_definition" {
  value = aws_batch_job_definition.worker_slim.name
}
