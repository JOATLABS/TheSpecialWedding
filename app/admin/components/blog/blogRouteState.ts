export type BlogRouteState =
  | { viewMode: 'list'; articleId?: never }
  | { viewMode: 'create'; articleId?: never }
  | { viewMode: 'edit'; articleId: string };

type SearchParamReader = {
  get(name: string): string | null;
};

export function getBlogRouteState(searchParams: SearchParamReader): BlogRouteState {
  const articleId = searchParams.get('blogArticle')?.trim();
  if (articleId) {
    return { viewMode: 'edit', articleId };
  }

  if (searchParams.get('blogMode') === 'create') {
    return { viewMode: 'create' };
  }

  return { viewMode: 'list' };
}

export function buildBlogRouteSearch(
  currentSearch: string | URLSearchParams,
  state: BlogRouteState,
): string {
  const params = new URLSearchParams(
    typeof currentSearch === 'string' ? currentSearch : currentSearch.toString(),
  );

  params.set('tab', 'blog');

  if (state.viewMode === 'edit') {
    params.set('blogArticle', state.articleId);
    params.delete('blogMode');
  } else if (state.viewMode === 'create') {
    params.set('blogMode', 'create');
    params.delete('blogArticle');
  } else {
    params.delete('blogArticle');
    params.delete('blogMode');
  }

  return params.toString();
}
