<template>
  <router-view v-if="$route.path === '/login'" />
  <el-container v-else class="layout">
    <el-aside width="236px" class="sidebar">
      <div class="brand">QQBot Admin</div>
      <el-menu router :default-active="$route.path" background-color="#0f172a" text-color="#cbd5e1" active-text-color="#fff">
        <el-menu-item index="/">仪表盘</el-menu-item>
        <el-menu-item index="/groups">群管理</el-menu-item>
        <el-menu-item index="/llm">模型设置</el-menu-item>
        <el-menu-item index="/logs">日志中心</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="topbar">新一代 QQ 群机器人 MVP</el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

