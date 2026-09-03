<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { listAccounts, getAccount, createAccount, updateAccount, deleteAccount, type AccountItem } from '@/api/accounts'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { toast } from '@/components/ui/toast'
import { Users, Pencil, Trash2, Plus, FileText, ExternalLink as LinkIcon } from 'lucide-vue-next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const { t } = useI18n()
const router = useRouter()

const accounts = ref<AccountItem[]>([])
const isLoading = ref(false)
const isSaving = ref(false)

const isCreateDialogOpen = ref(false)
const isEditDialogOpen = ref(false)
const isDeleteDialogOpen = ref(false)

const newName = ref('')
const newContent = ref('')
const editName = ref('')
const editContent = ref('')
const deleteName = ref('')

async function fetchAccounts() {
  isLoading.value = true
  try {
    accounts.value = await listAccounts()
  } catch (e) {
    toast({ title: t('accounts.toasts.loadFailed'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isLoading.value = false
  }
}

function openCreateDialog() {
  newName.value = ''
  newContent.value = ''
  isCreateDialogOpen.value = true
}

async function openEditDialog(name: string) {
  isSaving.value = true
  try {
    const detail = await getAccount(name)
    editName.value = detail.name
    editContent.value = detail.content
    isEditDialogOpen.value = true
  } catch (e) {
    toast({ title: t('accounts.toasts.loadContentFailed'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isSaving.value = false
  }
}

function openDeleteDialog(name: string) {
  deleteName.value = name
  isDeleteDialogOpen.value = true
}

function goCreateTask(name: string) {
  router.push({ path: '/tasks', query: { account: name, create: '1' } })
}

async function handleCreateAccount() {
  if (!newName.value.trim() || !newContent.value.trim()) {
    toast({ title: t('accounts.toasts.incomplete'), description: t('accounts.toasts.createDescriptionRequired'), variant: 'destructive' })
    return
  }
  isSaving.value = true
  try {
    await createAccount({ name: newName.value.trim(), content: newContent.value.trim() })
    toast({ title: t('accounts.toasts.created') })
    isCreateDialogOpen.value = false
    await fetchAccounts()
  } catch (e) {
    toast({ title: t('accounts.toasts.createFailed'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isSaving.value = false
  }
}

async function handleUpdateAccount() {
  if (!editContent.value.trim()) {
    toast({ title: t('accounts.toasts.contentRequired'), description: t('accounts.toasts.updateDescriptionRequired'), variant: 'destructive' })
    return
  }
  isSaving.value = true
  try {
    await updateAccount(editName.value, editContent.value.trim())
    toast({ title: t('accounts.toasts.updated') })
    isEditDialogOpen.value = false
    await fetchAccounts()
  } catch (e) {
    toast({ title: t('accounts.toasts.updateFailed'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isSaving.value = false
  }
}

async function handleDeleteAccount() {
  isSaving.value = true
  try {
    await deleteAccount(deleteName.value)
    toast({ title: t('accounts.toasts.deleted') })
    isDeleteDialogOpen.value = false
    await fetchAccounts()
  } catch (e) {
    toast({ title: t('accounts.toasts.deleteFailed'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isSaving.value = false
  }
}

onMounted(fetchAccounts)
</script>

<template>
  <div class="space-y-3">
    <header class="xy-card-flat flex items-center gap-2 p-2.5">
      <span
        class="flex h-7 w-7 items-center justify-center rounded-xl"
        style="background-color: hsl(56 100% 52%)"
      >
        <Users class="h-4 w-4 text-slate-900" />
      </span>
      <h1 class="truncate text-base font-black text-foreground">{{ t('accounts.title') }}</h1>
      <span class="xy-chip">{{ accounts.length }}</span>
      <button type="button" class="xy-btn-primary ml-auto h-9 text-[13px]" @click="openCreateDialog">
        <Plus class="h-3.5 w-3.5" />
        {{ t('accounts.add') }}
      </button>
    </header>

    <!-- Cookie 引导�?-->
    <section class="xy-card-flat border-[#ffe60f]/40 p-3">
      <h2 class="mb-2 text-[13px] font-bold text-foreground">{{ t('accounts.cookieGuide.title') }}</h2>
      <ol class="space-y-1 text-[12px] leading-relaxed text-slate-600">
        <li>
          {{ t('accounts.cookieGuide.step1Prefix') }}
          <a
            class="font-semibold"
            style="color: hsl(var(--op))"
            href="https://chromewebstore.google.com/detail/xianyu-login-state-extrac/eidlpfjiodpigmfcahkmlenhppfklcoa"
            target="_blank"
            rel="noopener noreferrer"
          >{{ t('accounts.cookieGuide.extension') }}
            <LinkIcon class="inline h-3 w-3" />
          </a>
        </li>
        <li>
          {{ t('accounts.cookieGuide.step2Prefix') }}
          <a
            class="font-semibold"
            style="color: hsl(var(--op))"
            href="https://www.goofish.com"
            target="_blank"
            rel="noopener noreferrer"
          >{{ t('accounts.cookieGuide.website') }}
            <LinkIcon class="inline h-3 w-3" />
          </a>
        </li>
        <li>{{ t('accounts.cookieGuide.step3') }}</li>
        <li>{{ t('accounts.cookieGuide.step4') }}</li>
        <li>{{ t('accounts.cookieGuide.step5') }}</li>
      </ol>
    </section>

    <!-- 账号列表 -->
    <section>
      <header class="mb-2 flex items-baseline justify-between">
        <h2 class="text-[13px] font-bold text-foreground">{{ t('accounts.list.title') }}</h2>
        <p class="text-[11px] text-slate-500">{{ t('accounts.list.description') }}</p>
      </header>

      <div v-if="isLoading" class="xy-card py-10 text-center text-sm text-slate-500">
        {{ t('common.loading') }}
      </div>
      <div v-else-if="accounts.length === 0" class="xy-card py-10 text-center text-sm text-slate-500">
        {{ t('accounts.list.empty') }}
      </div>

      <div v-else class="grid gap-2 sm:grid-cols-2">
        <article
          v-for="account in accounts"
          :key="account.name"
          class="xy-card flex flex-col gap-2 p-3"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <h3 class="truncate text-[14px] font-bold text-foreground">{{ account.name }}</h3>
              <p class="mt-0.5 flex items-center gap-1 truncate text-[11px] text-slate-500">
                <FileText class="h-3 w-3" />
                <span class="truncate">{{ account.path }}</span>
              </p>
            </div>
            <button
              type="button"
              class="xy-btn-ghost h-8 px-2 text-[12px]"
              @click="goCreateTask(account.name)"
            >
              + {{ t('accounts.list.createTask') }}
            </button>
          </div>
          <div class="flex gap-1.5">
            <button
              type="button"
              class="xy-btn-outline h-7 flex-1 text-[12px]"
              @click="openEditDialog(account.name)"
            >
              <Pencil class="h-3 w-3" />
              {{ t('accounts.list.update') }}
            </button>
            <button
              type="button"
              class="xy-btn-outline h-7 flex-1 text-[12px] text-rose-500"
              @click="openDeleteDialog(account.name)"
            >
              <Trash2 class="h-3 w-3" />
              {{ t('accounts.list.delete') }}
            </button>
          </div>
        </article>
      </div>
    </section>

    <Dialog v-model:open="isCreateDialogOpen">
      <DialogContent class="max-w-[640px]">
        <DialogHeader>
          <DialogTitle>{{ t('accounts.createDialog.title') }}</DialogTitle>
          <DialogDescription>{{ t('accounts.createDialog.description') }}</DialogDescription>
        </DialogHeader>
        <div class="space-y-3">
          <div class="grid gap-1.5">
            <Label>{{ t('accounts.createDialog.name') }}</Label>
            <Input v-model="newName" :placeholder="t('accounts.createDialog.namePlaceholder')" />
          </div>
          <div class="grid gap-1.5">
            <Label>{{ t('accounts.createDialog.jsonContent') }}</Label>
            <Textarea v-model="newContent" class="min-h-[200px]" :placeholder="t('accounts.createDialog.jsonPlaceholder')" />
          </div>
        </div>
        <DialogFooter>
          <button type="button" class="xy-btn-outline" @click="isCreateDialogOpen = false">{{ t('common.cancel') }}</button>
          <button type="button" class="xy-btn-primary" :disabled="isSaving" @click="handleCreateAccount">
            {{ isSaving ? t('common.saving') : t('common.save') }}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="isEditDialogOpen">
      <DialogContent class="max-w-[640px]">
        <DialogHeader>
          <DialogTitle>{{ t('accounts.editDialog.title', { name: editName }) }}</DialogTitle>
          <DialogDescription>{{ t('accounts.editDialog.description') }}</DialogDescription>
        </DialogHeader>
        <div class="grid gap-1.5">
          <Label>{{ t('accounts.createDialog.jsonContent') }}</Label>
          <Textarea v-model="editContent" class="min-h-[200px]" />
        </div>
        <DialogFooter>
          <button type="button" class="xy-btn-outline" @click="isEditDialogOpen = false">{{ t('common.cancel') }}</button>
          <button type="button" class="xy-btn-primary" :disabled="isSaving" @click="handleUpdateAccount">
            {{ isSaving ? t('common.saving') : t('common.save') }}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="isDeleteDialogOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ t('accounts.deleteDialog.title') }}</DialogTitle>
          <DialogDescription>{{ t('accounts.deleteDialog.description', { name: deleteName }) }}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <button type="button" class="xy-btn-outline" @click="isDeleteDialogOpen = false">{{ t('common.cancel') }}</button>
          <button type="button" class="xy-btn-danger" :disabled="isSaving" @click="handleDeleteAccount">
            {{ isSaving ? t('accounts.deleteDialog.deleting') : t('accounts.list.delete') }}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>




