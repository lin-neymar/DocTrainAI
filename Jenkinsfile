pipeline {
    agent any

    // 防并发构建（同机 2C4G，内存保护）
    options {
        disableConcurrentBuilds()
    }

    environment {
        REGISTRY  = 'crpi-8kb0sh7oyiobdzwv.cn-shenzhen.personal.cr.aliyuncs.com'
        NAMESPACE = 'doctrain'
        SERVER_IMAGE = "${REGISTRY}/${NAMESPACE}/server"
        WEB_IMAGE    = "${REGISTRY}/${NAMESPACE}/web"
    }

    stages {
        // ① 检出代码
        stage('Checkout') {
            steps { checkout scm }
        }

        // ② 登录 ACR（凭证 ID 'acr-credentials' 步骤 8 创建）
        stage('ACR Login') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'acr-credentials',
                    usernameVariable: 'ACR_USER', passwordVariable: 'ACR_PASS')]) {
                    sh 'echo "${ACR_PASS}" | docker login --username=${ACR_USER} --password-stdin ${REGISTRY}'
                }
            }
        }

        // ③ 构建 server：一次 build 双 tag（BUILD_NUMBER 唯一版本 + latest 部署引用）
        stage('Build Server Image') {
            steps {
                sh "docker build -f server/Dockerfile -t ${SERVER_IMAGE}:${BUILD_NUMBER} -t ${SERVER_IMAGE}:latest ."
            }
        }

        // ④ 构建 web：同上
        stage('Build Web Image') {
            steps {
                sh "docker build -f web/Dockerfile -t ${WEB_IMAGE}:${BUILD_NUMBER} -t ${WEB_IMAGE}:latest ."
            }
        }

        // ⑤ 推送 ACR：server/web × BUILD_NUMBER/latest 共四次
        stage('Push to ACR') {
            steps {
                sh "docker push ${SERVER_IMAGE}:${BUILD_NUMBER}"
                sh "docker push ${SERVER_IMAGE}:latest"
                sh "docker push ${WEB_IMAGE}:${BUILD_NUMBER}"
                sh "docker push ${WEB_IMAGE}:latest"
            }
        }

        // ⑥ 部署：注入 ACR 镜像名 + TAG，显式 -f compose.yaml 滚动更新
        stage('Deploy Rolling Update') {
            steps {
                sh """
                    cp compose.yaml /opt/doctrain/compose.yaml
                    cd /opt/doctrain
                    SERVER_IMAGE=${SERVER_IMAGE} WEB_IMAGE=${WEB_IMAGE} TAG=latest docker compose -f compose.yaml pull
                    SERVER_IMAGE=${SERVER_IMAGE} WEB_IMAGE=${WEB_IMAGE} TAG=latest docker compose -f compose.yaml up -d
                """
            }
        }
    }
}