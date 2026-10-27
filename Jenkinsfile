pipeline {
    agent any

    triggers { githubPush() }          // fired by the GitHub webhook

    options { timeout(time: 10, unit: 'MINUTES') }

    environment {
        COMPOSE = 'docker compose -p caredesk_ci -f docker-compose.jenkins.yml'
        APP_URL = 'http://localhost:8081'
    }

    stages {
        stage('Fetch code') {
            steps {
                checkout scm
                script {
                    // e-mail of the person who made the push
                    env.PUSHER_EMAIL = sh(returnStdout: true,
                        script: "git log -1 --pretty=format:%ae").trim()
                    env.PUSHER_NAME = sh(returnStdout: true,
                        script: "git log -1 --pretty=format:%an").trim()
                }
            }
        }

        stage('Sanity check (Docker Pipeline)') {
            steps {
                script {
                    docker.image('python:3.12-slim').inside('-e HOME=/tmp') {
                        sh 'pip install --user -q -r requirements.txt && python manage.py check'
                    }
                }
            }
        }

        stage('Build & deploy containers') {
            steps {
                sh '${COMPOSE} down || true'
                sh '${COMPOSE} up -d'
            }
        }

        stage('Verify app is up') {
            steps {
                sh '''
                  for i in $(seq 1 30); do
                    if curl -fsS -o /dev/null ${APP_URL}/; then echo "App is up"; exit 0; fi
                    echo "waiting ($i)..."; sleep 5
                  done
                  ${COMPOSE} logs --tail=50 ci_web
                  exit 1
                '''
            }
        }
    }

    post {
        always {
            emailext(
                to: "${env.PUSHER_EMAIL}",
                subject: "[CareDesk CI] ${currentBuild.currentResult}: build #${env.BUILD_NUMBER}",
                body: """Hi ${env.PUSHER_NAME},

Build #${env.BUILD_NUMBER} of ${env.JOB_NAME} finished with status: ${currentBuild.currentResult}

Details: ${env.BUILD_URL}
Console: ${env.BUILD_URL}console
App (Part II): http://<EC2-PUBLIC-IP>:8081
"""
            )
        }
    }
}
