import { afterEach, expect, it, vi } from "vitest";
vi.mock("./supabase", () => ({supabase:{auth:{getSession:vi.fn().mockResolvedValue({data:{session:{access_token:"token"}}})}}}));
import { loadLoans } from "./loans";
afterEach(() => vi.unstubAllGlobals());
it("loads all authenticated pages without caching private data", async () => {
 const fetchMock=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>({items:[{id:1}],has_more:true})}).mockResolvedValueOnce({ok:true,json:async()=>({items:[{id:2}],has_more:false})});
 vi.stubGlobal("fetch",fetchMock);
 expect(await loadLoans()).toEqual([{id:1},{id:2}]);
 expect(fetchMock).toHaveBeenNthCalledWith(2,"/api/loans?limit=100&offset=100",expect.objectContaining({cache:"no-store",headers:{Authorization:"Bearer token"}}));
});
